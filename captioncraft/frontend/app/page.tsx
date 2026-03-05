'use client';

import { useState, useCallback } from 'react';
import { X, RotateCcw } from 'lucide-react';
import Header from '@/components/Header';
import VideoUploader from '@/components/VideoUploader';
import VideoPreview from '@/components/VideoPreview';
import CaptionStyleSelector from '@/components/CaptionStyleSelector';
import FontSelector from '@/components/FontSelector';
import PositionSelector from '@/components/PositionSelector';
import LanguageSelector from '@/components/LanguageSelector';
import GenerateButton from '@/components/GenerateButton';
import ProgressIndicator from '@/components/ProgressIndicator';
import DownloadButton from '@/components/DownloadButton';
import { 
  type CaptionSettings, 
  type ProcessingJob, 
  type CaptionStyle, 
  type FontFamily, 
  type CaptionPosition,
  type CaptionLanguage
} from '@/lib/types';

type AppState = 'upload' | 'customize' | 'processing' | 'complete';

export default function Home() {
  // App state
  const [appState, setAppState] = useState<AppState>('upload');
  
  // Video state
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoPreviewUrl, setVideoPreviewUrl] = useState<string | null>(null);
  
  // Caption settings
  const [settings, setSettings] = useState<CaptionSettings>({
    style: 'classic',
    font: 'Montserrat',
    position: 'bottom',
    language: 'hi',  // Default to Hindi
  });
  
  // Processing state
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);

  // Handle video selection
  const handleVideoSelect = useCallback((file: File, previewUrl: string) => {
    setVideoFile(file);
    setVideoPreviewUrl(previewUrl);
    setAppState('customize');
  }, []);

  // Update settings
  const handleStyleChange = useCallback((style: CaptionStyle) => {
    setSettings(prev => ({ ...prev, style }));
  }, []);

  const handleFontChange = useCallback((font: FontFamily) => {
    setSettings(prev => ({ ...prev, font }));
  }, []);

  const handlePositionChange = useCallback((position: CaptionPosition) => {
    setSettings(prev => ({ ...prev, position }));
  }, []);

  const handleLanguageChange = useCallback((language: CaptionLanguage) => {
    setSettings(prev => ({ ...prev, language }));
  }, []);

  // Call backend API to process video
  const handleGenerate = useCallback(async () => {
    if (!videoFile) return;

    setAppState('processing');
    
    try {
      // Step 1: Upload video (just the file, no settings)
      const uploadFormData = new FormData();
      uploadFormData.append('file', videoFile);  // Backend expects 'file', not 'video'

      setJob({ id: 'uploading', status: 'uploading', progress: 10 });

      const uploadRes = await fetch('/api/upload', {
        method: 'POST',
        body: uploadFormData,
      });

      if (!uploadRes.ok) {
        const error = await uploadRes.json();
        throw new Error(error.error || 'Upload failed');
      }

      const uploadData = await uploadRes.json();
      const videoId = uploadData.video_id;
      console.log('Video uploaded:', videoId);

      setJob({ id: videoId, status: 'extracting', progress: 25 });

      // Step 2: Start processing with settings
      const processRes = await fetch('/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_id: videoId,
          style: settings.style,
          font: settings.font,
          position: settings.position,
          language: settings.language,
        }),
      });

      if (!processRes.ok) {
        const error = await processRes.json();
        throw new Error(error.error || 'Processing start failed');
      }

      const processData = await processRes.json();
      const jobId = processData.job_id;
      console.log('Processing started:', jobId);

      // Step 3: Poll for status
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`/api/status/${jobId}`);
          const statusData = await statusRes.json();

          setJob({
            id: jobId,
            status: statusData.status,
            progress: statusData.progress || 0,
          });

          if (statusData.status === 'completed' || statusData.status === 'complete') {
            clearInterval(pollInterval);
            setResultUrl(`/api/download/${jobId}`);
            setAppState('complete');
          } else if (statusData.status === 'failed') {
            clearInterval(pollInterval);
            alert('Processing failed: ' + (statusData.error || 'Unknown error'));
            setAppState('customize');
          }
        } catch (err) {
          console.error('Polling error:', err);
        }
      }, 2000);

    } catch (error: any) {
      alert('Error: ' + error.message);
      console.error(error);
      setAppState('customize');
    }
  }, [videoFile, videoPreviewUrl, settings]);

  // Reset and start over
  const handleReset = useCallback(() => {
    if (videoPreviewUrl) {
      URL.revokeObjectURL(videoPreviewUrl);
    }
    setVideoFile(null);
    setVideoPreviewUrl(null);
    setSettings({
      style: 'classic',
      font: 'Montserrat',
      position: 'bottom',
      language: 'hi',  // Reset to Hindi default
    });
    setJob(null);
    setResultUrl(null);
    setAppState('upload');
  }, [videoPreviewUrl]);

  // Remove current video (go back to upload)
  const handleRemoveVideo = useCallback(() => {
    if (videoPreviewUrl) {
      URL.revokeObjectURL(videoPreviewUrl);
    }
    setVideoFile(null);
    setVideoPreviewUrl(null);
    setAppState('upload');
  }, [videoPreviewUrl]);

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      
      <main className="flex-1 container mx-auto px-4 py-8">
        {/* Upload State */}
        {appState === 'upload' && (
          <div className="max-w-2xl mx-auto space-y-8">
            <div className="text-center space-y-4">
              <h2 className="text-4xl md:text-5xl font-bold">
                <span className="gradient-text">Add Captions</span>
                <br />
                to Your Videos
              </h2>
              <p className="text-gray-400 text-lg max-w-md mx-auto">
                Upload a video and we&apos;ll automatically transcribe and add 
                beautiful captions in your chosen style.
              </p>
            </div>
            
            <VideoUploader onVideoSelect={handleVideoSelect} />
            
            <div className="text-center text-sm text-gray-500">
              <p>Supports MP4, MOV, WebM • Max 100MB • Free tier: 5 videos/month</p>
            </div>
          </div>
        )}

        {/* Customize State */}
        {appState === 'customize' && videoPreviewUrl && (
          <div className="max-w-6xl mx-auto">
            <div className="grid lg:grid-cols-2 gap-8">
              {/* Left: Preview */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-2xl font-bold text-white">Preview</h2>
                  <button
                    onClick={handleRemoveVideo}
                    className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
                  >
                    <X className="w-4 h-4" />
                    Remove video
                  </button>
                </div>
                
                <VideoPreview 
                  videoUrl={videoPreviewUrl} 
                  settings={settings}
                />
                
                {videoFile && (
                  <div className="text-center text-sm text-gray-500">
                    <p>{videoFile.name}</p>
                    <p>{(videoFile.size / (1024 * 1024)).toFixed(2)} MB</p>
                  </div>
                )}
              </div>

              {/* Right: Settings */}
              <div className="space-y-6">
                <h2 className="text-2xl font-bold text-white">Customize</h2>
                
                <div className="space-y-6 bg-gray-800/30 rounded-2xl p-6 border border-gray-700/50">
                  <LanguageSelector
                    selected={settings.language}
                    onSelect={handleLanguageChange}
                  />
                  
                  <div className="border-t border-gray-700/50" />
                  
                  <CaptionStyleSelector
                    selected={settings.style}
                    onSelect={handleStyleChange}
                  />
                  
                  <div className="border-t border-gray-700/50" />
                  
                  <FontSelector
                    selected={settings.font}
                    onSelect={handleFontChange}
                  />
                  
                  <div className="border-t border-gray-700/50" />
                  
                  <PositionSelector
                    selected={settings.position}
                    onSelect={handlePositionChange}
                  />
                </div>

                <GenerateButton onClick={handleGenerate} />
              </div>
            </div>
          </div>
        )}

        {/* Processing State */}
        {appState === 'processing' && job && (
          <div className="max-w-md mx-auto space-y-8">
            <div className="text-center space-y-4">
              <h2 className="text-3xl font-bold text-white">
                Creating your captions...
              </h2>
              <p className="text-gray-400">
                This usually takes about a minute. Don&apos;t close this page.
              </p>
            </div>
            
            <ProgressIndicator job={job} />
          </div>
        )}

        {/* Complete State */}
        {appState === 'complete' && resultUrl && (
          <div className="max-w-2xl mx-auto space-y-8">
            <div className="text-center space-y-4">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-500/20 text-green-500 mb-4">
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-3xl font-bold text-white">
                Your video is ready!
              </h2>
              <p className="text-gray-400">
                Download your captioned video and share it everywhere.
              </p>
            </div>
            
            {/* Result preview */}
            <div className="bg-gray-800/50 rounded-2xl p-6 border border-gray-700">
              <VideoPreview 
                videoUrl={resultUrl} 
                settings={settings}
                captionText="Captions added!"
              />
            </div>
            
            <DownloadButton 
              resultUrl={resultUrl} 
              filename={`captioned-${videoFile?.name || 'video.mp4'}`}
            />
            
            <div className="text-center">
              <button
                onClick={handleReset}
                className="inline-flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
                Create another video
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-6">
        <div className="container mx-auto px-4 text-center text-sm text-gray-500">
          <p>Made with ❤️ for content creators</p>
        </div>
      </footer>
    </div>
  );
}
