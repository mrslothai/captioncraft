'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Save, Download, Loader2 } from 'lucide-react';
import Link from 'next/link';

interface Word {
  text: string;
  start: number; // ms
  end: number;   // ms
}

interface Segment {
  id: number;
  startMs: number;
  endMs: number;
  originalText: string;
  editedText: string;
  wordIndices: number[]; // indices into original words array
}

type PageState = 'loading' | 'ready' | 'saving' | 'complete' | 'error';

function formatTimestamp(ms: number): string {
  const totalSecs = ms / 1000;
  const mins = Math.floor(totalSecs / 60);
  const secs = (totalSecs % 60).toFixed(2).padStart(5, '0');
  return `${mins}:${secs}`;
}

function groupWordsIntoSegments(words: Word[]): Segment[] {
  if (!words.length) return [];
  const segments: Segment[] = [];
  let currentGroup: number[] = [];
  let segId = 0;

  for (let i = 0; i < words.length; i++) {
    currentGroup.push(i);
    const nextWord = words[i + 1];
    const gapToNext = nextWord ? nextWord.start - words[i].end : Infinity;
    // New segment if: gap > 500ms or 4 words collected
    if (currentGroup.length >= 4 || gapToNext > 500) {
      const indices = [...currentGroup];
      const text = indices.map(idx => words[idx].text).join(' ');
      segments.push({
        id: segId++,
        startMs: words[indices[0]].start,
        endMs: words[indices[indices.length - 1]].end,
        originalText: text,
        editedText: text,
        wordIndices: indices,
      });
      currentGroup = [];
    }
  }
  // Flush remaining
  if (currentGroup.length > 0) {
    const indices = [...currentGroup];
    const text = indices.map(idx => words[idx].text).join(' ');
    segments.push({
      id: segId++,
      startMs: words[indices[0]].start,
      endMs: words[indices[indices.length - 1]].end,
      originalText: text,
      editedText: text,
      wordIndices: indices,
    });
  }
  return segments;
}

export default function EditPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.jobId as string;

  const [pageState, setPageState] = useState<PageState>('loading');
  const [segments, setSegments] = useState<Segment[]>([]);
  const [originalWords, setOriginalWords] = useState<Word[]>([]);
  const [activeTab, setActiveTab] = useState<'transcript' | 'captions' | 'edit'>('transcript');
  const [saveProgress, setSaveProgress] = useState(0);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const videoRef = useRef<HTMLVideoElement>(null);

  // Load transcript
  useEffect(() => {
    if (!jobId) return;
    fetch(`/api/transcript/${jobId}`)
      .then(r => r.json())
      .then(data => {
        if (data.words && Array.isArray(data.words)) {
          setOriginalWords(data.words);
          setSegments(groupWordsIntoSegments(data.words));
          setPageState('ready');
        } else {
          setErrorMsg(data.detail || 'Failed to load transcript');
          setPageState('error');
        }
      })
      .catch(e => {
        setErrorMsg(e.message);
        setPageState('error');
      });
  }, [jobId]);

  const handleSegmentEdit = useCallback((segId: number, newText: string) => {
    setSegments(prev =>
      prev.map(s => s.id === segId ? { ...s, editedText: newText } : s)
    );
  }, []);

  const seekVideo = useCallback((ms: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = ms / 1000;
      videoRef.current.play().catch(() => {});
    }
  }, []);

  // Build edited words array from segments
  const buildEditedWords = useCallback((): Word[] => {
    const editedWords: Word[] = [...originalWords];
    for (const seg of segments) {
      const editedTokens = seg.editedText.trim().split(/\s+/);
      // Map edited tokens back to word slots (best effort)
      seg.wordIndices.forEach((wIdx, i) => {
        if (i < editedTokens.length) {
          editedWords[wIdx] = { ...editedWords[wIdx], text: editedTokens[i] };
        }
      });
    }
    return editedWords;
  }, [segments, originalWords]);

  const handleSave = useCallback(async () => {
    setPageState('saving');
    setSaveProgress(10);
    const editedWords = buildEditedWords();
    try {
      const res = await fetch(`/api/reprocess/${jobId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ words: editedWords, style: 'classic', font: 'Montserrat', position: 'bottom' }),
      });
      if (!res.ok) throw new Error('Reprocess start failed');
      setSaveProgress(20);

      // Poll for completion
      const poll = setInterval(async () => {
        try {
          const statusRes = await fetch(`/api/status/${jobId}`);
          const status = await statusRes.json();
          const progress = Math.min(20 + Math.round(status.progress * 0.8), 99);
          setSaveProgress(progress);
          if (status.status === 'completed') {
            clearInterval(poll);
            setSaveProgress(100);
            setDownloadUrl(`/api/download/${jobId}`);
            setPageState('complete');
          } else if (status.status === 'failed') {
            clearInterval(poll);
            setErrorMsg(status.error || 'Reprocessing failed');
            setPageState('error');
          }
        } catch { /* ignore polling errors */ }
      }, 2000);
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Save failed');
      setPageState('error');
    }
  }, [buildEditedWords, jobId]);

  const hasEdits = segments.some(s => s.editedText !== s.originalText);

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Top Bar */}
      <header className="bg-gray-900 border-b border-gray-800 px-4 py-3 flex items-center gap-4 sticky top-0 z-10">
        <Link href="/" className="text-gray-400 hover:text-white transition-colors flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back</span>
        </Link>

        <div className="font-semibold text-white flex-1 truncate">
          Edit Transcript
          <span className="ml-2 text-xs text-gray-500 font-mono">{jobId?.slice(0, 8)}</span>
        </div>

        {/* Tab Nav */}
        <div className="hidden sm:flex bg-gray-800 rounded-lg p-1 gap-1">
          {(['transcript', 'captions', 'edit'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-1 rounded text-sm capitalize transition-colors ${
                activeTab === tab
                  ? 'bg-gray-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          {pageState === 'complete' && downloadUrl && (
            <a
              href={downloadUrl}
              download
              className="flex items-center gap-1 px-3 py-1.5 bg-green-600 hover:bg-green-700 rounded-lg text-sm transition-colors"
            >
              <Download className="w-4 h-4" />
              Download
            </a>
          )}
          <button
            onClick={handleSave}
            disabled={pageState === 'loading' || pageState === 'saving' || !hasEdits}
            className="flex items-center gap-1 px-4 py-1.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm transition-colors"
          >
            {pageState === 'saving' ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Saving...</>
            ) : (
              <><Save className="w-4 h-4" /> Save</>
            )}
          </button>
        </div>
      </header>

      {/* Progress bar */}
      {pageState === 'saving' && (
        <div className="h-1 bg-gray-800">
          <div
            className="h-full bg-purple-500 transition-all duration-500"
            style={{ width: `${saveProgress}%` }}
          />
        </div>
      )}

      {/* Main Content */}
      {pageState === 'loading' && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-4">
            <Loader2 className="w-10 h-10 animate-spin text-purple-500 mx-auto" />
            <p className="text-gray-400">Loading transcript...</p>
          </div>
        </div>
      )}

      {pageState === 'error' && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-4">
            <p className="text-red-400 text-lg">Error: {errorMsg}</p>
            <p className="text-gray-500 text-sm">Make sure the job has finished processing.</p>
            <Link href="/" className="text-purple-400 hover:underline">← Go back</Link>
          </div>
        </div>
      )}

      {(pageState === 'ready' || pageState === 'saving' || pageState === 'complete') && (
        <div className="flex-1 flex overflow-hidden" style={{ height: 'calc(100vh - 57px)' }}>
          {/* LEFT PANEL — Transcript */}
          <div className="w-2/5 bg-gray-900 border-r border-gray-800 flex flex-col overflow-hidden">
            <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between">
              <span className="text-sm text-gray-400">
                {segments.length} segments
                {hasEdits && <span className="ml-2 text-yellow-400 text-xs">• unsaved changes</span>}
              </span>
            </div>
            <div className="flex-1 overflow-y-auto">
              {segments.map(seg => {
                const edited = seg.editedText !== seg.originalText;
                return (
                  <div
                    key={seg.id}
                    className={`flex items-start gap-3 px-4 py-2 hover:bg-gray-800 border-b border-gray-800/50 group transition-colors ${
                      edited ? 'bg-yellow-500/5 border-l-2 border-l-yellow-500' : ''
                    }`}
                  >
                    <button
                      onClick={() => seekVideo(seg.startMs)}
                      className="text-gray-400 text-xs font-mono mt-1 whitespace-nowrap hover:text-purple-400 transition-colors flex-shrink-0 pt-1"
                      title="Click to seek"
                    >
                      {formatTimestamp(seg.startMs)}
                    </button>
                    <input
                      type="text"
                      value={seg.editedText}
                      onChange={e => handleSegmentEdit(seg.id, e.target.value)}
                      className={`flex-1 bg-transparent text-white text-sm py-0.5 px-1 rounded focus:outline-none focus:bg-gray-700 transition-colors ${
                        edited ? 'text-yellow-200' : ''
                      }`}
                    />
                  </div>
                );
              })}
            </div>
          </div>

          {/* RIGHT PANEL — Video Player */}
          <div className="flex-1 bg-gray-950 flex flex-col items-center justify-center p-6 gap-6">
            <div className="w-full max-w-lg">
              <video
                ref={videoRef}
                src={`/api/video/${jobId}`}
                controls
                className="w-full rounded-xl bg-black shadow-2xl"
                preload="metadata"
              />
            </div>

            {pageState === 'complete' && downloadUrl && (
              <a
                href={downloadUrl}
                download
                className="flex items-center gap-2 px-6 py-3 bg-green-600 hover:bg-green-700 rounded-xl text-white font-semibold transition-colors shadow-lg"
              >
                <Download className="w-5 h-5" />
                Download Captioned Video
              </a>
            )}

            {pageState === 'saving' && (
              <div className="text-center space-y-2">
                <Loader2 className="w-8 h-8 animate-spin text-purple-500 mx-auto" />
                <p className="text-gray-400 text-sm">Regenerating captions... {saveProgress}%</p>
              </div>
            )}

            {pageState === 'ready' && (
              <p className="text-gray-500 text-sm text-center max-w-xs">
                Edit segments on the left, then click <span className="text-purple-400">Save</span> to regenerate captions.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
