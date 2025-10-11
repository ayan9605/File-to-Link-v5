// static/admin.js
class AdminPanel {
    constructor() {
        this.token = localStorage.getItem('adminToken');
        this.currentPage = 1;
        this.currentSearch = '';
        this.currentLimit = 50;
        this.charts = {};
        this.statsData = {};
        
        this.initializeEventListeners();
        this.checkAuthentication();
    }

    initializeEventListeners() {
        // Login form
        document.getElementById('loginForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleLogin();
        });

        // Logout button
        document.getElementById('logoutBtn').addEventListener('click', () => {
            this.handleLogout();
        });

        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.loadAllData();
        });

        // Search functionality
        document.getElementById('searchBtn').addEventListener('click', () => {
            this.handleSearch();
        });

        document.getElementById('searchInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.handleSearch();
            }
        });

        // Clear search
        document.getElementById('clearSearch').addEventListener('click', () => {
            this.clearSearch();
        });

        // Pagination
        document.getElementById('prevPage').addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.loadFiles();
            }
        });

        document.getElementById('nextPage').addEventListener('click', () => {
            this.currentPage++;
            this.loadFiles();
        });
    }

    checkAuthentication() {
        if (this.token) {
            this.showAdminPanel();
            this.loadAllData();
        } else {
            this.showLoginScreen();
        }
    }

    showLoginScreen() {
        document.getElementById('loginScreen').classList.remove('hidden');
        document.getElementById('adminPanel').classList.add('hidden');
    }

    showAdminPanel() {
        document.getElementById('loginScreen').classList.add('hidden');
        document.getElementById('adminPanel').classList.remove('hidden');
    }

    async handleLogin() {
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        const errorElement = document.getElementById('loginError');

        try {
            this.showLoading(true);
            
            const response = await fetch('/admin/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json();

            if (data.status === 'success') {
                this.token = data.token;
                localStorage.setItem('adminToken', this.token);
                errorElement.textContent = '';
                errorElement.className = 'success-message';
                errorElement.textContent = 'Login successful!';
                
                setTimeout(() => {
                    this.showAdminPanel();
                    this.loadAllData();
                }, 1000);
            } else {
                errorElement.className = 'error-message';
                errorElement.textContent = data.detail || 'Login failed';
            }
        } catch (error) {
            errorElement.className = 'error-message';
            errorElement.textContent = 'Network error. Please try again.';
        } finally {
            this.showLoading(false);
        }
    }

    async handleLogout() {
        try {
            await this.apiCall('/auth/logout', {
                method: 'POST'
            });
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            this.token = null;
            localStorage.removeItem('adminToken');
            this.showLoginScreen();
        }
    }

    async loadAllData() {
        this.showLoading(true);
        try {
            await Promise.all([
                this.loadOverviewStats(),
                this.loadFiles(),
                this.loadChartData()
            ]);
            this.updateLastUpdated();
        } catch (error) {
            console.error('Error loading data:', error);
            this.showError('Failed to load data. Please try again.');
        } finally {
            this.showLoading(false);
        }
    }

    async loadOverviewStats() {
        try {
            const response = await this.apiCall('/stats');
            if (response.data) {
                this.statsData = response.data;
                this.updateStatsCards(response.data);
            }
        } catch (error) {
            console.error('Error loading stats:', error);
            throw error;
        }
    }

    async loadFiles() {
        try {
            let url = `/files?page=${this.currentPage}&limit=${this.currentLimit}`;
            if (this.currentSearch) {
                url += `&search=${encodeURIComponent(this.currentSearch)}`;
            }

            const response = await this.apiCall(url);
            if (response.data) {
                this.renderFilesTable(response.data.files);
                this.updatePagination(response.data.pagination);
            }
        } catch (error) {
            console.error('Error loading files:', error);
            throw error;
        }
    }

    async loadChartData() {
        try {
            const response = await this.apiCall('/charts');
            if (response.data) {
                this.renderCharts(response.data);
            }
        } catch (error) {
            console.error('Error loading chart data:', error);
            throw error;
        }
    }

    updateStatsCards(stats) {
        document.getElementById('totalFiles').textContent = stats.total_files.toLocaleString();
        document.getElementById('totalDownloads').textContent = stats.total_downloads.toLocaleString();
        document.getElementById('totalStorage').textContent = this.formatFileSize(stats.total_storage);
        document.getElementById('recentUploads').textContent = stats.recent_uploads.toLocaleString();
        document.getElementById('uniqueUsers').textContent = stats.unique_users.toLocaleString();
        document.getElementById('redisInfo').textContent = stats.redis_memory;
    }

    renderFilesTable(files) {
        const tbody = document.getElementById('filesTableBody');
        
        if (files.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align: center; padding: 40px; color: #6c757d;">
                        No files found. ${this.currentSearch ? 'Try a different search term.' : 'No files have been uploaded yet.'}
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = '';

        files.forEach(file => {
            const row = document.createElement('tr');
            
            row.innerHTML = `
                <td title="${this.escapeHtml(file.file_name)}">
                    <div style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        ${this.escapeHtml(file.file_name)}
                    </div>
                </td>
                <td>${this.formatFileSize(file.file_size)}</td>
                <td>
                    <span class="file-type-badge ${file.file_type}">
                        ${file.file_type.toUpperCase()}
                    </span>
                </td>
                <td>
                    <div style="max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        ${file.user_name || 'Unknown'}
                    </div>
                </td>
                <td>${new Date(file.upload_date).toLocaleDateString()}</td>
                <td>
                    <span class="download-count ${file.download_count > 0 ? 'has-downloads' : ''}">
                        ${file.download_count}
                    </span>
                </td>
                <td>
                    <button class="btn btn-danger btn-sm" onclick="admin.deleteFile('${file.file_id}')" title="Delete File">
                        🗑️ Delete
                    </button>
                </td>
            `;
            
            tbody.appendChild(row);
        });
    }

    updatePagination(pagination) {
        const pageInfo = document.getElementById('pageInfo');
        const prevBtn = document.getElementById('prevPage');
        const nextBtn = document.getElementById('nextPage');

        pageInfo.textContent = `Page ${pagination.page} of ${pagination.pages}`;
        prevBtn.disabled = pagination.page <= 1;
        nextBtn.disabled = pagination.page >= pagination.pages;

        // Update button states
        prevBtn.classList.toggle('btn-secondary', !prevBtn.disabled);
        prevBtn.classList.toggle('btn-outline', prevBtn.disabled);
        nextBtn.classList.toggle('btn-secondary', !nextBtn.disabled);
        nextBtn.classList.toggle('btn-outline', nextBtn.disabled);
    }

    renderCharts(chartData) {
        this.renderUploadsChart(chartData.uploads_over_time);
        this.renderDownloadsChart(chartData.downloads_over_time);
        this.renderFileTypesChart(chartData.file_types);
    }

    renderUploadsChart(uploadsData) {
        const ctx = document.getElementById('uploadsChart').getContext('2d');
        
        if (this.charts.uploads) {
            this.charts.uploads.destroy();
        }

        const labels = uploadsData.map(item => {
            const date = new Date(item._id);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        });
        const data = uploadsData.map(item => item.count);

        this.charts.uploads = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Uploads per Day',
                    data: data,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#667eea',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'File Uploads (Last 7 Days)',
                        font: {
                            size: 16,
                            weight: 'bold'
                        }
                    },
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        });
    }

    renderDownloadsChart(downloadsData) {
        const ctx = document.getElementById('downloadsChart').getContext('2d');
        
        if (this.charts.downloads) {
            this.charts.downloads.destroy();
        }

        const labels = downloadsData.map(item => {
            const date = new Date(item._id);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        });
        const data = downloadsData.map(item => item.count);

        this.charts.downloads = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Downloads per Day',
                    data: data,
                    backgroundColor: '#764ba2',
                    borderColor: '#667eea',
                    borderWidth: 1,
                    borderRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'File Downloads (Last 7 Days)',
                        font: {
                            size: 16,
                            weight: 'bold'
                        }
                    },
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        });
    }

    renderFileTypesChart(fileTypesData) {
        const ctx = document.getElementById('fileTypesChart').getContext('2d');
        
        if (this.charts.fileTypes) {
            this.charts.fileTypes.destroy();
        }

        const labels = fileTypesData.map(item => item._id || 'unknown');
        const data = fileTypesData.map(item => item.count);

        this.charts.fileTypes = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: [
                        '#667eea', '#764ba2', '#f093fb', '#ff5858',
                        '#f093fb', '#ffdd00', '#24fe41', '#ff6b6b',
                        '#4ecdc4', '#45b7d1', '#96ceb4', '#feca57'
                    ],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'File Types Distribution',
                        font: {
                            size: 16,
                            weight: 'bold'
                        }
                    },
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true
                        }
                    }
                },
                cutout: '60%'
            }
        });
    }

    async deleteFile(fileId) {
        if (!confirm('Are you sure you want to delete this file? This action cannot be undone.')) {
            return;
        }

        try {
            this.showLoading(true);
            const response = await this.apiCall(`/files/${fileId}`, {
                method: 'DELETE'
            });

            if (response.status === 'success') {
                this.showSuccess('File deleted successfully!');
                await this.loadAllData(); // Refresh all data
            } else {
                this.showError('Error deleting file: ' + (response.detail || 'Unknown error'));
            }
        } catch (error) {
            this.showError('Error deleting file: ' + error.message);
        } finally {
            this.showLoading(false);
        }
    }

    handleSearch() {
        this.currentSearch = document.getElementById('searchInput').value.trim();
        this.currentPage = 1;
        this.loadFiles();
    }

    clearSearch() {
        document.getElementById('searchInput').value = '';
        this.currentSearch = '';
        this.currentPage = 1;
        this.loadFiles();
    }

    async apiCall(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Content-Type': 'application/json'
            }
        };

        // Convert relative URLs to absolute for admin API
        if (url.startsWith('/')) {
            url = `/admin/api${url}`;
        }

        const response = await fetch(url, { ...defaultOptions, ...options });
        
        if (response.status === 401) {
            this.handleLogout();
            throw new Error('Authentication failed');
        }

        if (!response.ok) {
            const errorText = await response.text();
            let errorDetail = `HTTP error! status: ${response.status}`;
            try {
                const errorData = JSON.parse(errorText);
                errorDetail = errorData.detail || errorDetail;
            } catch {
                errorDetail = errorText || errorDetail;
            }
            throw new Error(errorDetail);
        }

        return await response.json();
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    updateLastUpdated() {
        const now = new Date();
        document.getElementById('lastUpdated').textContent = 
            `Last updated: ${now.toLocaleTimeString()}`;
    }

    showLoading(show) {
        document.getElementById('loadingSpinner').classList.toggle('hidden', !show);
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showNotification(message, type) {
        // Remove existing notifications
        const existingNotifications = document.querySelectorAll('.notification');
        existingNotifications.forEach(notification => notification.remove());

        const notification = document.createElement('div');
        notification.className = `notification ${type}-message`;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 8px;
            z-index: 1001;
            max-width: 400px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            animation: slideInRight 0.3s ease;
        `;
        
        notification.textContent = message;
        document.body.appendChild(notification);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideOutRight 0.3s ease';
                setTimeout(() => notification.remove(), 300);
            }
        }, 5000);
    }
}

// Add CSS for animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    .file-type-badge {
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        background: #e9ecef;
        color: #495057;
    }
    
    .file-type-badge.document { background: #d4edda; color: #155724; }
    .file-type-badge.video { backgr