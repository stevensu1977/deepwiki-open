import React, { useEffect, useRef, useState } from 'react';
import { FaSearchPlus, FaSearchMinus, FaSearch, FaTimes } from 'react-icons/fa';

// Mermaid will be dynamically imported to avoid SSR issues
let mermaid: any = null;

// Initialize mermaid configuration
const initializeMermaid = async () => {
  if (typeof window === 'undefined') return null;
  
  if (!mermaid) {
    const mermaidModule = await import('mermaid');
    mermaid = mermaidModule.default;
    
    mermaid.initialize({
      startOnLoad: false,
      theme: 'base',
      securityLevel: 'loose',
      suppressErrorRendering: false,
      logLevel: 'debug',
      maxTextSize: 100000,
      htmlLabels: true,
      themeVariables: {
        primaryColor: '#ffffff',
        primaryTextColor: '#000000',
        primaryBorderColor: '#333333',
        lineColor: '#333333',
        secondaryColor: '#ffffff',
        tertiaryColor: '#ffffff',
        background: '#ffffff',
        mainBkg: '#ffffff',
        secondBkg: '#ffffff',
        tertiaryBkg: '#ffffff',
        // Ensure custom node colors are respected
        nodeBkg: '#ffffff',
        nodeTextColor: '#000000',
        nodeBorder: '#333333',
        // Flowchart specific
        cScale0: '#ff9999',
        cScale1: '#bbbbff',
        cScale2: '#bbffbb',
        cScale3: '#ffbbff',
        cScale4: '#ffbbbb',
        cScale5: '#bbffff'
      },
      flowchart: {
        htmlLabels: true,
        curve: 'basis',
        nodeSpacing: 60,
        rankSpacing: 60,
        padding: 20,
      },
    });
  }
  
  return mermaid;
};

interface MermaidProps {
  chart: string;
  className?: string;
  zoomingEnabled?: boolean;
}

const Mermaid: React.FC<MermaidProps> = ({ chart, className = '', zoomingEnabled = false }) => {
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1); // Start with 1x zoom for natural display

  const idRef = useRef(`mermaid-${Math.random().toString(36).substring(2, 9)}`);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!showModal) return;

      switch (event.key) {
        case 'Escape':
          setShowModal(false);
          break;
        case '+':
        case '=':
          event.preventDefault();
          handleZoomIn();
          break;
        case '-':
          event.preventDefault();
          handleZoomOut();
          break;
        case '0':
          event.preventDefault();
          handleResetZoom();
          break;
      }
    };

    if (showModal) {
      document.addEventListener('keydown', handleKeyDown);
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    };
  }, [showModal]);

  useEffect(() => {
    if (!chart) return;

    let isMounted = true;

    const renderChart = async () => {
      if (!isMounted) return;

      try {
        setError(null);
        setSvg('');
        setIsLoading(true);

        console.log('Rendering Mermaid chart:', chart);

        // Initialize mermaid if not already done
        const mermaidInstance = await initializeMermaid();
        if (!mermaidInstance) {
          throw new Error('Failed to initialize Mermaid');
        }

        // Clean the chart content
        const cleanChart = chart.trim();

        // Render the chart
        const { svg: renderedSvg } = await mermaidInstance.render(idRef.current, cleanChart);

        if (!isMounted) return;

        console.log('Mermaid rendered successfully');

        // Simple SVG processing
        let processedSvg = renderedSvg;
        
        // Make the SVG responsive
        processedSvg = processedSvg.replace(
          /<svg([^>]*)>/,
          '<svg$1 style="max-width: 100%; height: auto;">'
        );

        setSvg(processedSvg);
        setIsLoading(false);

      } catch (err) {
        console.error('Mermaid rendering error:', err);

        const errorMessage = err instanceof Error ? err.message : String(err);

        if (isMounted) {
          setError(`Failed to render diagram: ${errorMessage}`);
          setIsLoading(false);
          console.log('Setting error state:', errorMessage);
        }
      }
    };

    // Add a small delay to ensure DOM is ready
    setTimeout(() => {
      renderChart();
    }, 100);

    return () => {
      isMounted = false;
    };
  }, [chart]);

  if (error) {
    return (
      <div className={`border border-red-300 dark:border-red-800 rounded-md p-3 ${className}`}>
        <div className="flex items-center mb-2">
          <div className="text-red-500 dark:text-red-400 text-xs font-medium flex items-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Diagram rendering error
          </div>
        </div>
        <div className="text-xs text-red-600 dark:text-red-400 mb-2">{error}</div>
        <pre className="text-xs overflow-auto p-2 bg-gray-100 dark:bg-gray-800 rounded border">
          {chart}
        </pre>
        <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          The diagram contains syntax errors and cannot be rendered.
        </div>
      </div>
    );
  }

  if (isLoading || !svg) {
    return (
      <div className={`flex justify-center items-center p-4 ${className}`}>
        <div className="animate-pulse text-gray-400 dark:text-gray-600 text-xs">Rendering diagram...</div>
      </div>
    );
  }

  const handleClick = () => {
    if (zoomingEnabled) {
      setShowModal(true);
      setZoomLevel(1); // Start with 1x zoom when opening modal
    }
  };

  const handleZoomIn = () => {
    setZoomLevel(prev => Math.min(prev + 0.25, 3)); // Max zoom 3x
  };

  const handleZoomOut = () => {
    setZoomLevel(prev => Math.max(prev - 0.25, 0.5)); // Min zoom 0.5x
  };

  const handleResetZoom = () => {
    setZoomLevel(1); // Reset to 1x zoom (100% display)
  };

  const handleWheel = (event: React.WheelEvent) => {
    if (event.ctrlKey || event.metaKey) {
      event.preventDefault();
      if (event.deltaY < 0) {
        handleZoomIn();
      } else {
        handleZoomOut();
      }
    }
  };

  return (
    <>
      <div className={`w-full max-w-full ${className}`}>
        <div className="flex justify-center overflow-auto text-center my-2">
          <div
            dangerouslySetInnerHTML={{
              __html: svg.replace(
                /<svg([^>]*)>/,
                '<svg$1 style="width: 100%; height: auto; min-width: 600px; min-height: 400px; transform: scale(1.5); transform-origin: center;">'
              )
            }}
            onClick={handleClick}
            className={zoomingEnabled ? 'cursor-pointer hover:opacity-80 transition-opacity' : ''}
            title={zoomingEnabled ? 'Click to enlarge' : undefined}
            style={{
              width: '100%',
              minHeight: '500px',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center'
            }}
          />
        </div>
      </div>

      {/* Full-screen modal */}
      {showModal && zoomingEnabled && (
        <div
          className="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center z-50 p-4"
          onClick={() => setShowModal(false)}
          onWheel={handleWheel}
        >
          <div className="relative w-[95vw] h-[95vh] bg-white dark:bg-gray-900 rounded-lg shadow-2xl flex flex-col">
            {/* Header with controls */}
            <div className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-4 py-2 flex justify-between items-center rounded-t-lg">
              <div className="flex items-center space-x-3">
                <h3 className="text-base font-semibold text-gray-900 dark:text-white">Mermaid Diagram</h3>
                <div className="text-xs text-gray-400 dark:text-gray-500 hidden xl:block">
                  Use +/- keys, Ctrl+scroll, or buttons to zoom
                </div>
              </div>

              {/* Zoom controls */}
              <div className="flex items-center bg-gray-50 dark:bg-gray-800 rounded-md px-1 py-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleZoomOut();
                  }}
                  className={`p-1.5 rounded transition-all duration-200 ${
                    zoomLevel <= 0.5
                      ? 'text-gray-300 dark:text-gray-600 cursor-not-allowed'
                      : 'text-gray-600 hover:text-gray-800 dark:text-gray-300 dark:hover:text-gray-100 hover:bg-white dark:hover:bg-gray-700'
                  }`}
                  title="Zoom Out (-)"
                  disabled={zoomLevel <= 0.5}
                >
                  <FaSearchMinus className="h-3.5 w-3.5" />
                </button>

                <div className="w-px h-5 bg-gray-200 dark:bg-gray-600 mx-1"></div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleResetZoom();
                  }}
                  className="px-2 py-1.5 text-sm text-gray-600 hover:text-gray-800 dark:text-gray-300 dark:hover:text-gray-100 rounded hover:bg-white dark:hover:bg-gray-700 transition-all duration-200 flex items-center space-x-1.5 min-w-[70px] justify-center"
                  title="Reset Zoom (0)"
                >
                  <FaSearch className="h-3 w-3" />
                  <span className="font-medium text-xs">{Math.round(zoomLevel * 100)}%</span>
                </button>

                <div className="w-px h-5 bg-gray-200 dark:bg-gray-600 mx-1"></div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleZoomIn();
                  }}
                  className={`p-1.5 rounded transition-all duration-200 ${
                    zoomLevel >= 3
                      ? 'text-gray-300 dark:text-gray-600 cursor-not-allowed'
                      : 'text-gray-600 hover:text-gray-800 dark:text-gray-300 dark:hover:text-gray-100 hover:bg-white dark:hover:bg-gray-700'
                  }`}
                  title="Zoom In (+)"
                  disabled={zoomLevel >= 3}
                >
                  <FaSearchPlus className="h-3.5 w-3.5" />
                </button>

                <div className="w-px h-5 bg-gray-200 dark:bg-gray-600 mx-1.5"></div>

                <button
                  onClick={() => setShowModal(false)}
                  className="p-1.5 text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400 rounded hover:bg-red-50 dark:hover:bg-red-900/20 transition-all duration-200"
                  title="Close (ESC)"
                >
                  <FaTimes className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            {/* Diagram content with scroll */}
            <div className="flex-1 overflow-auto flex justify-center items-center bg-gray-50 dark:bg-gray-900">
              <div
                className="transition-transform duration-200 ease-in-out"
                style={{
                  transform: `scale(${zoomLevel})`,
                  transformOrigin: 'center center',
                  width: '90vw',
                  height: '80vh',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center'
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <div
                  dangerouslySetInnerHTML={{
                    __html: svg.replace(
                      /<svg([^>]*)>/,
                      '<svg$1 style="width: 100%; height: 100%; max-width: none; max-height: none;">'
                    )
                  }}
                  style={{
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center'
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default Mermaid;
