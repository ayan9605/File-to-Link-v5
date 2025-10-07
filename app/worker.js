// Cloudflare Worker - CDN Proxy for File Downloads
// Caches files and provides ultra-fast global delivery

const BACKEND_URL = "https://file-to-link-v5.onrender.com";

// Cache configuration
const CACHE_TTL = 3600; // 1 hour
const STALE_WHILE_REVALIDATE = 86400; // 24 hours
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB cache limit

addEventListener('fetch', event => {
    event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
    const url = new URL(request.url);
    const cache = caches.default;
    
    try {
        // Only handle specific paths
        if (!url.pathname.startsWith('/dl/') && !url.pathname.startsWith('/api/')) {
            return new Response('Not found', { status: 404 });
        }
        
        // Construct target URL
        const targetUrl = `${BACKEND_URL}${url.pathname}${url.search}`;
        
        // Create cache key
        const cacheKey = new Request(targetUrl, {
            method: 'GET',
            headers: {
                'Accept': request.headers.get('Accept') || '*/*',
                'Accept-Encoding': request.headers.get('Accept-Encoding') || 'gzip, deflate, br'
            }
        });
        
        // Try to get from cache first
        let response = await cache.match(cacheKey);
        
        if (response) {
            // Cache hit - add cache headers
            response = new Response(response.body, response);
            response.headers.set('CF-Cache-Status', 'HIT');
            response.headers.set('X-Served-By', 'cloudflare-worker');
            
            // Handle conditional requests
            const ifNoneMatch = request.headers.get('If-None-Match');
            const etag = response.headers.get('ETag');
            
            if (ifNoneMatch && etag && ifNoneMatch === etag) {
                return new Response(null, {
                    status: 304,
                    headers: {
                        'CF-Cache-Status': 'HIT',
                        'ETag': etag,
                        'Cache-Control': response.headers.get('Cache-Control') || 'public, max-age=3600'
                    }
                });
            }
            
            return response;
        }
        
        // Cache miss - fetch from origin
        const originRequest = new Request(targetUrl, {
            method: request.method,
            headers: {
                'User-Agent': 'CloudflareWorker/1.0',
                'Accept': request.headers.get('Accept') || '*/*',
                'Accept-Encoding': 'gzip, deflate, br',
                'X-Forwarded-For': request.headers.get('CF-Connecting-IP') || request.headers.get('X-Forwarded-For') || '0.0.0.0',
                'X-Real-IP': request.headers.get('CF-Connecting-IP') || '0.0.0.0',
            }
        });
        
        // Add Range header if present (for partial content)
        const rangeHeader = request.headers.get('Range');
        if (rangeHeader) {
            originRequest.headers.set('Range', rangeHeader);
        }
        
        // Fetch from origin
        response = await fetch(originRequest);
        
        if (!response.ok) {
            return new Response(`Origin error: ${response.status}`, { 
                status: response.status,
                headers: {
                    'Content-Type': 'text/plain',
                    'CF-Cache-Status': 'MISS'
                }
            });
        }
        
        // Clone response for caching
        const responseClone = response.clone();
        
        // Prepare response headers
        const newResponse = new Response(response.body, response);
        
        // Set cache headers
        newResponse.headers.set('CF-Cache-Status', 'MISS');
        newResponse.headers.set('X-Served-By', 'cloudflare-worker');
        newResponse.headers.set('Access-Control-Allow-Origin', '*');
        newResponse.headers.set('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS');
        newResponse.headers.set('Access-Control-Allow-Headers', 'Range, Content-Type, Authorization');
        
        // Enhanced cache control
        if (url.pathname.startsWith('/dl/')) {
            newResponse.headers.set('Cache-Control', `public, max-age=${CACHE_TTL}, stale-while-revalidate=${STALE_WHILE_REVALIDATE}, immutable`);
        } else {
            newResponse.headers.set('Cache-Control', `public, max-age=300, stale-while-revalidate=600`); // 5min for API
        }
        
        // Add Brotli compression hint
        if (!newResponse.headers.has('Content-Encoding')) {
            newResponse.headers.set('Content-Encoding', 'br');
        }
        
        // Security headers
        newResponse.headers.set('X-Content-Type-Options', 'nosniff');
        newResponse.headers.set('X-Frame-Options', 'SAMEORIGIN');
        newResponse.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
        
        // Cache the response (only for successful GET requests and reasonable file sizes)
        if (request.method === 'GET' && 
            response.status === 200 && 
            !rangeHeader && // Don't cache partial responses
            url.pathname.startsWith('/dl/')) {
            
            const contentLength = response.headers.get('Content-Length');
            const fileSize = contentLength ? parseInt(contentLength) : 0;
            
            if (fileSize <= MAX_FILE_SIZE) {
                // Cache for files under size limit
                event.waitUntil(cache.put(cacheKey, responseClone));
            }
        }
        
        return newResponse;
        
    } catch (error) {
        console.error('Worker error:', error);
        
        return new Response(JSON.stringify({
            error: 'Worker error',
            message: error.message,
            timestamp: new Date().toISOString()
        }), {
            status: 500,
            headers: {
                'Content-Type': 'application/json',
                'CF-Cache-Status': 'ERROR'
            }
        });
    }
}

// Handle OPTIONS requests for CORS
addEventListener('fetch', event => {
    if (event.request.method === 'OPTIONS') {
        event.respondWith(handleOptions(event.request));
    }
});

async function handleOptions(request) {
    const corsHeaders = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, HEAD, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, Range',
        'Access-Control-Max-Age': '86400', // 24 hours
    };
    
    return new Response(null, {
        status: 204,
        headers: corsHeaders
    });
}

// Analytics and monitoring
addEventListener('scheduled', event => {
    event.waitUntil(handleScheduled(event));
});

async function handleScheduled(event) {
    // Clean up old cache entries or perform maintenance
    // This runs on Cloudflare cron triggers
    console.log('Scheduled maintenance triggered');
}
