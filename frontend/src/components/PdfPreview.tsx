import { ChevronLeft, ChevronRight, FileWarning } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.mjs?url';

type PdfPreviewProps = {
  fileUrl: string;
};

type PreviewStatus = 'loading' | 'ready' | 'error';

export function PdfPreview({ fileUrl }: PdfPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [pageCount, setPageCount] = useState(0);
  const [status, setStatus] = useState<PreviewStatus>('loading');
  const [message, setMessage] = useState('Loading PDF preview...');

  useEffect(() => {
    let cancelled = false;
    let loadedPdf: PDFDocumentProxy | null = null;

    async function loadPdf() {
      setStatus('loading');
      setMessage('Loading PDF preview...');
      setPdf(null);
      setPageNumber(1);
      try {
        const pdfjs = await import('pdfjs-dist');
        pdfjs.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;
        const loadingTask = pdfjs.getDocument({ url: fileUrl });
        loadedPdf = await loadingTask.promise;
        if (cancelled) {
          await loadedPdf.destroy();
          return;
        }
        setPdf(loadedPdf);
        setPageCount(loadedPdf.numPages);
      } catch {
        if (!cancelled) {
          setStatus('error');
          setMessage('The embedded PDF preview could not be rendered.');
        }
      }
    }

    void loadPdf();

    return () => {
      cancelled = true;
      if (loadedPdf) {
        void loadedPdf.destroy();
      }
    };
  }, [fileUrl]);

  useEffect(() => {
    if (!pdf) return;

    let cancelled = false;
    let renderTask: RenderTask | null = null;
    const currentPdf = pdf;

    async function renderPage() {
      const canvas = canvasRef.current;
      if (!canvas) return;

      setStatus('loading');
      setMessage(`Rendering page ${pageNumber}...`);

      try {
        const page = await currentPdf.getPage(pageNumber);
        if (cancelled) return;

        const containerWidth = canvas.parentElement?.clientWidth ?? 860;
        const unscaledViewport = page.getViewport({ scale: 1 });
        const scale = Math.min(1.8, Math.max(0.8, (containerWidth - 48) / unscaledViewport.width));
        const viewport = page.getViewport({ scale });
        const pixelRatio = window.devicePixelRatio || 1;
        const context = canvas.getContext('2d');
        if (!context) {
          throw new Error('Canvas is unavailable.');
        }

        canvas.width = Math.floor(viewport.width * pixelRatio);
        canvas.height = Math.floor(viewport.height * pixelRatio);
        canvas.style.width = `${Math.floor(viewport.width)}px`;
        canvas.style.height = `${Math.floor(viewport.height)}px`;

        context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
        context.clearRect(0, 0, viewport.width, viewport.height);

        renderTask = page.render({ canvas: null, canvasContext: context, viewport });
        await renderTask.promise;

        if (!cancelled) {
          setStatus('ready');
          setMessage(`Showing page ${pageNumber} of ${currentPdf.numPages}`);
        }
      } catch {
        if (!cancelled) {
          setStatus('error');
          setMessage('The embedded PDF preview could not be rendered.');
        }
      }
    }

    void renderPage();

    return () => {
      cancelled = true;
      if (renderTask) {
        renderTask.cancel();
      }
    };
  }, [pageNumber, pdf]);

  return (
    <div className="bg-slate-100">
      <div className="flex min-h-[660px] flex-col">
        <div className="flex h-12 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4">
          <p className="text-sm font-medium text-slate-700">{message}</p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Previous page"
              disabled={!pdf || pageNumber <= 1}
              onClick={() => setPageNumber((current) => Math.max(1, current - 1))}
              className="focus-ring grid h-8 w-8 place-items-center rounded border border-slate-300 bg-white text-slate-700 hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronLeft aria-hidden="true" size={16} />
            </button>
            <span className="min-w-16 text-center text-sm text-slate-700">
              {pageCount > 0 ? `${pageNumber} / ${pageCount}` : '-'}
            </span>
            <button
              type="button"
              aria-label="Next page"
              disabled={!pdf || pageNumber >= pageCount}
              onClick={() => setPageNumber((current) => Math.min(pageCount, current + 1))}
              className="focus-ring grid h-8 w-8 place-items-center rounded border border-slate-300 bg-white text-slate-700 hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronRight aria-hidden="true" size={16} />
            </button>
          </div>
        </div>

        <div className="flex flex-1 justify-center overflow-auto p-4">
          {status === 'error' ? (
            <div className="flex min-h-[520px] w-full items-center justify-center">
              <div className="max-w-sm text-center">
                <FileWarning aria-hidden="true" className="mx-auto mb-3 text-slate-400" size={32} />
                <p className="text-sm font-medium text-slate-800">PDF preview unavailable</p>
                <p className="mt-1 text-sm text-slate-600">Use Open PDF to view the file in a browser tab.</p>
              </div>
            </div>
          ) : (
            <canvas
              ref={canvasRef}
              title="Document preview"
              className="max-w-full self-start rounded border border-slate-300 bg-white shadow-sm"
            />
          )}
        </div>
      </div>
    </div>
  );
}
