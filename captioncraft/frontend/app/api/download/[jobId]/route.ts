import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8080';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params;

    // Forward to backend
    const response = await fetch(`${BACKEND_URL}/download/${jobId}`);

    if (!response.ok) {
      let errorMsg = 'Download failed';
      try {
        const error = await response.json();
        errorMsg = error.detail || errorMsg;
      } catch {}
      return NextResponse.json({ error: errorMsg }, { status: response.status });
    }

    // Stream binary video back to client
    const buffer = await response.arrayBuffer();
    return new NextResponse(buffer, {
      headers: {
        'Content-Type': 'video/mp4',
        'Content-Disposition': `attachment; filename="captioned-video.mp4"`,
        'Content-Length': response.headers.get('Content-Length') || '',
      },
    });

  } catch (error) {
    console.error('Download error:', error);
    return NextResponse.json(
      { error: 'Failed to generate download link. Is backend running?' },
      { status: 500 }
    );
  }
}
