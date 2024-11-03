import React, { useState, useEffect } from 'react';
import { AlertCircle, Clock, Download, RefreshCw } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

const ScraperDashboard = () => {
  const [selectedOption, setSelectedOption] = useState(null);
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [progress, setProgress] = useState(null);

  const scrapingOptions = [
    {
      id: 'quick',
      title: 'Quick Category Scan',
      description: 'Scrape specific category (100-200 products)',
      estimatedTime: '5-10 minutes',
      pages: '25-50',
      categories: ['Lighting', 'Wiring', 'Switches', 'Distribution']
    },
    {
      id: 'batch',
      title: 'Batch Processing',
      description: 'Scrape 1000 products at a time',
      estimatedTime: '45-60 minutes',
      pages: '250'
    },
    {
      id: 'full',
      title: 'Full Catalogue',
      description: 'Complete product catalogue (4000+ pages)',
      estimatedTime: '3.5-4.6 hours',
      pages: '4176',
      warning: 'This is a lengthy process. You can leave the page and return later to check progress.'
    }
  ];

  const startScraping = async () => {
    if (!selectedOption) return;
    
    const params = new URLSearchParams({
      type: selectedOption.id,
      ...(selectedOption.category && { category: selectedOption.category })
    });

    try {
      const response = await fetch(`/start-scrape?${params}`, { method: 'POST' });
      const data = await response.json();
      setJobId(data.job_id);
      setIsConfirmed(false);
    } catch (err) {
      console.error('Failed to start scraping:', err);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">ACDC Product Scraper</h1>
      
      {!jobId && !isConfirmed && (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold">Select Scraping Option:</h2>
          <div className="grid gap-4">
            {scrapingOptions.map((option) => (
              <div 
                key={option.id}
                className={`p-4 border rounded-lg cursor-pointer hover:border-blue-500 transition-colors
                  ${selectedOption?.id === option.id ? 'border-blue-500 bg-blue-50' : ''}`}
                onClick={() => setSelectedOption(option)}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold">{option.title}</h3>
                    <p className="text-gray-600">{option.description}</p>
                    <div className="mt-2 flex items-center text-sm text-gray-500">
                      <Clock className="h-4 w-4 mr-1" />
                      Estimated time: {option.estimatedTime}
                    </div>
                    <div className="mt-1 text-sm text-gray-500">
                      Pages to process: {option.pages}
                    </div>
                  </div>
                </div>

                {option.warning && (
                  <Alert className="mt-2">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>{option.warning}</AlertDescription>
                  </Alert>
                )}

                {option.categories && selectedOption?.id === option.id && (
                  <div className="mt-3">
                    <label className="text-sm font-medium">Select Category:</label>
                    <select 
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm"
                      onChange={(e) => setSelectedOption({...option, category: e.target.value})}
                    >
                      <option value="">Select a category...</option>
                      {option.categories.map(cat => (
                        <option key={cat} value={cat}>{cat}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            ))}
          </div>

          {selectedOption && (
            <div className="flex space-x-4">
              <button
                onClick={() => setIsConfirmed(true)}
                className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              >
                Continue with {selectedOption.title}
              </button>
              <button
                onClick={() => setSelectedOption(null)}
                className="px-4 py-2 border rounded hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      )}

      {!jobId && isConfirmed && (
        <div className="mt-6 p-4 border rounded">
          <h2 className="text-lg font-semibold mb-4">Confirm Scraping</h2>
          <p>You are about to start scraping with these settings:</p>
          <ul className="mt-2 mb-4 space-y-2">
            <li>Type: {selectedOption.title}</li>
            <li>Estimated Time: {selectedOption.estimatedTime}</li>
            {selectedOption.category && <li>Category: {selectedOption.category}</li>}
            <li>Pages to Process: {selectedOption.pages}</li>
          </ul>
          
          <div className="flex space-x-4">
            <button
              onClick={startScraping}
              className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
            >
              Start Scraping
            </button>
            <button
              onClick={() => setIsConfirmed(false)}
              className="px-4 py-2 border rounded hover:bg-gray-50"
            >
              Back
            </button>
          </div>
        </div>
      )}

      {jobId && progress && (
        <div className="mt-6 p-4 border rounded">
          <h2 className="text-lg font-semibold mb-4">Scraping Progress</h2>
          <div className="space-y-2">
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div 
                className="bg-blue-600 h-2.5 rounded-full transition-all duration-500"
                style={{ width: `${(progress.current_page / selectedOption.pages) * 100}%` }}
              ></div>
            </div>
            <p>Processing Page: {progress.current_page} of {selectedOption.pages}</p>
            <p>Products Scraped: {progress.total_products}</p>
            <p>Estimated Time Remaining: {progress.estimated_remaining}</p>
            
            {progress.status === 'completed' && (
              <a 
                href={`/download-results/${jobId}`}
                className="inline-flex items-center px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
              >
                <Download className="mr-2 h-4 w-4" />
                Download Results
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ScraperDashboard;
