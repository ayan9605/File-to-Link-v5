const BACKEND = "https://file-to-link-v5.onrender.com";
const CACHE_VERSION = 'v9-debug';
const CACHE_TTL = 7200;
const IMAGE_CACHE_TTL = 2592000;
const VIDEO_CACHE_TTL = 604800;

class RocketCDN {
    constructor() {
        this.cache = caches.default;
        this.imageExtensions = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg']);
        this.videoExtensions = new Set(['mp4', 'webm', 'avi', 'mov', 'mkv', 'm4v']);
        this.noCacheExtensions = new Set(['php', 'html', 'htm', 'js', 'css', 'json']);
    }

    async handleRequest(request) {
        const startTime = Date.now();
        
        try {
            // Handle CORS preflight immediately
            if (request.method === 'OPTIONS') {
                return this.corsResponse();
            }

            const url = new URL(request.url);
            
            console.log(`📨 Incoming request: ${request.method} ${url.pathname}`);
            
            // Only process download requests
            if (!url.pathname.startsWith('/dl/')) {
                console.log(`❌ Invalid path: ${url.pathname}`);
                return this.errorResponse(404, 'Endpoint Not Found');
            }

            const result = await this.processDownload(request, url);
            
            // Add performance header
            result.headers.set('X-Response-Time', `${Date.now() - startTime}ms`);
            console.log(`✅ Request completed in ${Date.now() - startTime}ms`);
            
            return result;
            
        } catch (error) {
            console.error(`💥 Request failed in ${Date.now() - startTime}ms:`, error);
            return this.errorResponse(503, `CDN Service Error: ${error.message}`);
        }
    }

    async processDownload(request, url) {
        const cacheKey = this.generateCacheKey(request);
        const fileInfo = this.analyzeFile(url.pathname);
        
        console.log(`🔍 File analysis:`, fileInfo);
        
        // Fast path: Check cache for cacheable content
        if (fileInfo.shouldCache) {
            const cached = await this.cache.match(cacheKey);
            if (cached) {
                console.log(`🚀 Cache HIT: ${url.pathname}`);
                return this.enhanceCachedResponse(cached, fileInfo);
            }
        }

        // Cache miss or non-cacheable - fetch from origin
        console.log(`⚡ Cache MISS: ${url.pathname}`);
        return await this.fetchFromOrigin(request, cacheKey, fileInfo, url);
    }

    async fetchFromOrigin(request, cacheKey, fileInfo, url) {
        try {
            // Use the direct route (without /api/v1 prefix)
            const targetUrl = `${BACKEND}${url.pathname}${url.search}`;
            console.log(`🌐 Fetching from origin: ${targetUrl}`);
            
            // Create new request with correct URL
            const originRequest = new Request(targetUrl, {
                method: request.method,
                headers: request.headers,
                redirect: 'follow'
            });

            const response = await this.fetchWithTimeout(originRequest);
            
            console.log(`📊 Origin response status: ${response.status}`);
            
            if (!response.ok) {
                console.log(`❌ Origin response error: ${response.status} ${response.statusText}`);
                return this.handleOriginError(response);
            }

            console.log(`✅ Origin fetch successful, caching response`);
            
            // Cache successful responses
            if (fileInfo.shouldCache && response.status === 200) {
                await this.cacheResponse(cacheKey, response, fileInfo);
            }

            return this.buildRocketResponse(response, fileInfo);
            
        } catch (error) {
            console.error('💥 Origin fetch error:', error);
            return this.errorResponse(503, `Origin Unavailable: ${error.message}`);
        }
    }

    async fetchWithTimeout(request, timeout = 15000) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => {
            console.log(`⏰ Request timeout after ${timeout}ms`);
            controller.abort();
        }, timeout);

        try {
            console.log(`🚀 Starting fetch to: ${request.url}`);
            const response = await fetch(request, {
                signal: controller.signal,
                cf: {
                    // Cloudflare performance optimizations
                    cacheEverything: false,
                    scrapeShield: false,
                    mirage: true,
                    polish: 'lossy'
                }
            });

            clearTimeout(timeoutId);
            console.log(`✅ Fetch completed: ${response.status}`);
            return response;
            
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.log(`⏰ Fetch timeout error`);
                throw new Error(`Origin timeout (${timeout}ms) - Backend might be down or slow`);
            }
            console.log(`💥 Fetch error:`, error);
            throw error;
        }
    }

    analyzeFile(pathname) {
        const extension = this.getFileExtension(pathname);
        const isImage = this.imageExtensions.has(extension);
        const isVideo = this.videoExtensions.has(extension);
        const shouldCache = !this.noCacheExtensions.has(extension) && 
                           (isImage || isVideo || extension === '');
        
        let cacheTTL = CACHE_TTL;
        if (isImage) cacheTTL = IMAGE_CACHE_TTL;
        if (isVideo) cacheTTL = VIDEO_CACHE_TTL;

        return {
            extension,
            isImage,
            isVideo,
            shouldCache,
            cacheTTL
        };
    }

    getFileExtension(pathname) {
        const match = pathname.match(/\.([a-z0-9]+)(?:[\?#]|$)/i);
        return match ? match[1].toLowerCase() : '';
    }

    generateCacheKey(request) {
        const url = new URL(request.url);
        return `${CACHE_VERSION}-${request.method}-${url.pathname}${url.search}`;
    }

    async cacheResponse(cacheKey, response, fileInfo) {
        try {
            const responseToCache = response.clone();
            
            const headers = new Headers(responseToCache.headers);
            
            // Optimize cache headers
            headers.set('Cache-Control', 
                `public, max-age=${fileInfo.cacheTTL}, stale-while-revalidate=86400, immutable`);
            headers.set('CDN-Cache-Control', `public, max-age=${fileInfo.cacheTTL}`);
            headers.set('Vary', 'Accept-Encoding');
            
            // Remove problematic headers
            headers.delete('Set-Cookie');
            headers.delete('X-Powered-By');
            
            // Add CDN info
            headers.set('X-CDN', 'Rocket-CDN');
            headers.set('X-Cache-TTL', fileInfo.cacheTTL.toString());

            const cacheResponse = new Response(responseToCache.body, {
                status: responseToCache.status,
                statusText: responseToCache.statusText,
                headers: headers
            });

            // Non-blocking cache write
            this.cache.put(cacheKey, cacheResponse).then(() => {
                console.log(`💾 Cached response for: ${cacheKey}`);
            }).catch(err => {
                console.error('💥 Cache write error:', err);
            });
            
        } catch (error) {
            console.error('💥 Cache processing error:', error);
        }
    }

    enhanceCachedResponse(cachedResponse, fileInfo) {
        const headers = new Headers(cachedResponse.headers);
        
        // Add performance headers
        headers.set('X-CDN-Cache', 'HIT');
        headers.set('X-Cache-Version', CACHE_VERSION);
        headers.set('X-Rocket', 'true');
        headers.set('Access-Control-Allow-Origin', '*');
        
        console.log(`🎯 Serving from cache`);
        
        return new Response(cachedResponse.body, {
            status: cachedResponse.status,
            statusText: cachedResponse.statusText,
            headers: headers
        });
    }

    buildRocketResponse(originResponse, fileInfo) {
        const headers = new Headers(originResponse.headers);
        
        // Clean headers
        this.cleanHeaders(headers);
        
        // Add CDN headers
        headers.set('X-CDN-Cache', 'MISS');
        headers.set('X-Cache-Version', CACHE_VERSION);
        headers.set('X-Rocket', 'true');
        headers.set('Access-Control-Allow-Origin', '*');
        
        // Optimize caching
        if (!headers.has('Cache-Control') && fileInfo.shouldCache) {
            headers.set('Cache-Control', 
                `public, max-age=${fileInfo.cacheTTL}, stale-while-revalidate=86400`);
        }
        
        console.log(`🎉 Building final response`);
        
        return new Response(originResponse.body, {
            status: originResponse.status,
            statusText: originResponse.statusText,
            headers: headers
        });
    }

    cleanHeaders(headers) {
        const headersToRemove = [
            'Set-Cookie', 'X-Powered-By', 'Server', 'Via',
            'X-Runtime', 'X-Rack-Cache', 'X-Request-Id'
        ];
        
        headersToRemove.forEach(header => headers.delete(header));
    }

    corsResponse() {
        return new Response(null, {
            status: 204,
            headers: {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Range, Cache-Control, If-None-Match',
                'Access-Control-Max-Age': '86400',
                'Access-Control-Expose-Headers': 'Content-Length, Content-Range',
                'Cache-Control': 'no-store'
            }
        });
    }

    handleOriginError(response) {
        const status = response.status;
        const errorMap = {
            400: 'Bad Request',
            401: 'Unauthorized', 
            403: 'Forbidden',
            404: 'File Not Found',
            413: 'File Too Large',
            500: 'Origin Server Error',
            502: 'Bad Gateway',
            503: 'Service Unavailable',
            504: 'Gateway Timeout'
        };

        const message = errorMap[status] || `Origin Error: ${status}`;
        console.log(`🎯 Origin error: ${status} - ${message}`);
        return this.errorResponse(status, message);
    }

    errorResponse(status, message) {
        console.log(`❌ Returning error: ${status} - ${message}`);
        return new Response(JSON.stringify({
            error: true,
            message: message,
            code: status,
            timestamp: new Date().toISOString(),
            cdn: 'Rocket-CDN',
            backend: BACKEND
        }), {
            status: status,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'no-store, max-age=0',
                'X-CDN-Error': 'true'
            }
        });
    }
}

// Global instance
const rocketCDN = new RocketCDN();

// Event listeners
addEventListener('fetch', event => {
    event.respondWith(rocketCDN.handleRequest(event.request));
});

// Test endpoint to verify worker is working
addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    
    // Add a test endpoint
    if (url.pathname === '/cdn-test') {
        event.respondWith(new Response(JSON.stringify({
            status: 'CDN Worker Active',
            version: CACHE_VERSION,
            backend: BACKEND,
            timestamp: new Date().toISOString()
        }), {
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }));
        return;
    }
    
    event.respondWith(rocketCDN.handleRequest(event.request));
});