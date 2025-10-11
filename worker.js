// cloudflare-worker.js
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;
    
    // Handle file downloads
    if (path.startsWith('/dl/')) {
      const fileId = path.split('/dl/')[1];
      const code = url.searchParams.get('code');
      
      if (!fileId || !code) {
        return new Response('Missing file ID or code', { status: 400 });
      }
      
      // Your Render server URL
      const renderUrl = 'https://file-to-link-v5.onrender.com'; // Replace with your actual URL
      
      try {
        // Proxy the request to your Render server
        const response = await fetch(`${renderUrl}/dl/${fileId}?code=${code}`, {
          headers: request.headers,
          cf: {
            // Cache everything for 24 hours
            cacheTtl: 86400,
            cacheEverything: true,
          }
        });
        
        // Clone response to modify headers
        const modifiedResponse = new Response(response.body, response);
        
        // Enhanced caching headers
        modifiedResponse.headers.set('Cache-Control', 'public, max-age=86400, s-maxage=86400');
        modifiedResponse.headers.set('CDN-Cache-Control', 'public, max-age=86400');
        modifiedResponse.headers.set('Vary', 'Accept-Encoding');
        
        // Add security headers
        modifiedResponse.headers.set('X-Content-Type-Options', 'nosniff');
        modifiedResponse.headers.set('X-Frame-Options', 'DENY');
        modifiedResponse.headers.set('X-XSS-Protection', '1; mode=block');
        
        return modifiedResponse;
        
      } catch (error) {
        return new Response('CDN Error: ' + error.message, { status: 500 });
      }
    }
    
    // Health check endpoint
    if (path === '/health') {
      return new Response(JSON.stringify({ 
        status: 'healthy', 
        service: 'FileToLink CDN v8.0',
        timestamp: Date.now()
      }), {
        headers: { 
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache'
        }
      });
    }
    
    // Default response
    return new Response('FileToLink CDN Worker v8.0\n\nUse /dl/{file_id}?code={code} to download files', {
      status: 200,
      headers: {
        'Content-Type': 'text/plain',
        'Cache-Control': 'no-cache'
      }
    });
  }
};