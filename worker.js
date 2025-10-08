const BACKEND = "https://file-to-linkv5.onrender.com";
const CACHE_VERSION = 'v5-rocket';
const CACHE_TTL = 7200; // 2 hours
const IMAGE_CACHE_TTL = 2592000; // 30 days
const VIDEO_CACHE_TTL = 604800; // 7 days

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
            
            // Only process download requests
            if (!url.pathname.startsWith('/dl/')) {
                return this.errorResponse(404, 'Endpoint Not Found');
            }

            const result = await this.processDownload(request, url);
            
            // Add performance header
            result.headers.set('X-Response-Time', `${Date.now() - startTime}ms`);
            
            return result;
            
        } catch (error) {
            console.error(`Request failed in ${Date.now() - startTime}ms:`, error);
            return this.errorResponse(503, 'CDN Service Error');
        }
    }

    async processDownload(request, url) {
        const cacheKey = this.generateCacheKey(request);
        const fileInfo = this.analyzeFile(url.pathname);
        
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
        return await this.fetchFromOrigin(request, cacheKey, fileInfo);
    }

    async fetchFromOrigin(request, cacheKey, fileInfo) {
        try {
            // Change the path to include /api/v1 for the backend
            const url = new URL(request.url);
            const target = `${BACKEND}/api/v1${url.pathname}${url.search}`;
            
            // Create a new request with the target URL
            const originRequest = new Request(target, request);
            
            const response = await this.fetchWithTimeout(originRequest);
            
            if (!response.ok) {
                return this.handleOriginError(response);
            }

            // Cache successful responses
            if (fileInfo.shouldCache && response.status === 200) {
                await this.cacheResponse(cacheKey, response, fileInfo);
            }

            return this.buildRocketResponse(response, fileInfo);
            
        } catch (error) {
            console.error('Origin fetch error:', error);
            return this.errorResponse(503, 'Origin Unavailable');
        }
    }

    async fetchWithTimeout(request, timeout = 8000) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        try {
            const response = await fetch(request, {
                signal: controller.signal,
                cf: {
                    // Cloudflare performance optimizations
                    cacheEverything: false,
                    scrapeShield: false,
                    mirage: true,
                    polish: 'lossy',
                    minify: {
                        javascript: true,
                        css: true,
                        html: true
                    }
                }
            });

            clearTimeout(timeoutId);
            return response;
            
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new Error(`Origin timeout (${timeout}ms)`);
            }
            throw error;
        }
    }

    // ... (rest of the methods remain the same)

}

// Global instance
const rocketCDN = new RocketCDN();

// Event listeners
addEventListener('fetch', event => {
    event.respondWith(rocketCDN.handleRequest(event.request));
});