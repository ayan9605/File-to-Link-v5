// Modern Admin Panel JavaScript
// Handles UI interactions, API calls, and real-time updates

class AdminDashboard {
    constructor() {
        this.currentSection = 'dashboard';
        this.charts = {};
        this.refreshInterval = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.initializeCharts();
        this.loadDashboardData();
        this.startAutoRefresh();
    }

    setupEventListeners() {
        // Sidebar navigation
        document.querySelectorAll('.menu-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const section = item.getAttribute('data-section');
                this.switchSection(section);
            });
        });

        // Sidebar toggle for mobile
        const sidebarToggle = document.getElementById('sidebarToggle');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => {
                document.querySelector('.sidebar').classList.toggle('open');
            });
        }

        // Refresh button
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshCurrentSection();
            });
        }

        // Search inputs
        const fileSearch = document.getElementById('fileSearch');
        if (fileSearch) {
            fileSearch.addEventListener('input', this.debounce(() => {
                this.loadFiles(1, fileSearch.value);
            }, 500));
        }

        const userSearch = document.getElementById('userSearch');
        if (userSearch) {
            userSearch.addEventListener('input', this.debounce(() => {
                this.loadUsers(1, userSearch.value);
            }, 500));
        }

        // Modal close
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-overlay') || e.target.classList.contains('modal-close')) {
                this.closeModal();
            }
        });

        // Escape key to close modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });
    }

    switchSection(section) {
        // Update active menu item
        document.querySelectorAll('.menu-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-section="${section}"]`).classList.add('active');

        // Update active section
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });
        document.getElementById(`${section}-section`).classList.add('active');

        // Update page title
        const titles = {
            dashboard: 'Dashboard',
            files: 'File Management',
            users: 'User Management',
            analytics: 'Analytics',
            settings: 'Settings',
            logs: 'Admin Logs'
        };

        document.querySelector('.page-title').textContent = titles[section] || section;
        
        // Update page subtitle
        const subtitles = {
            dashboard: 'System overview and statistics',
            files: 'Manage uploaded files and downloads',
            users: 'User accounts and permissions',
            analytics: 'Usage insights and trends',
            settings: 'System configuration',
            logs: 'Admin activity history'
        };
        
        document.querySelector('.page-subtitle').textContent = subtitles[section] || '';

        this.currentSection = section;
        this.loadSectionData(section);
    }

    loadSectionData(section) {
        switch (section) {
            case 'dashboard':
                this.loadDashboardData();
                break;
            case 'files':
                this.loadFiles();
                break;
            case 'users':
                this.loadUsers();
                break;
            case 'analytics':
                this.loadAnalytics();
                break;
            case 'logs':
                this.loadLogs();
                break;
        }
    }

    async loadDashboardData() {
        try {
            this.showLoading();
            
            const response = await fetch('/admin/api/stats');
            const stats = await response.json();
            
            // Update stat cards
            document.getElementById('totalFiles').textContent = stats.files.total.toLocaleString();
            document.getElementById('totalUsers').textContent = stats.users.total.toLocaleString();
            document.getElementById('totalDownloads').textContent = stats.recent_activity?.downloads_24h?.toLocaleString() || '0';
            document.getElementById('totalStorage').textContent = `${stats.storage.total_gb} GB`;
            
            // Update charts
            this.updateUploadChart(stats);
            this.updateDownloadChart(stats);
            
            // Load recent activity
            this.loadRecentActivity();
            
            this.hideLoading();
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
            this.showError('Failed to load dashboard data');
            this.hideLoading();
        }
    }

    async loadFiles(page = 1, search = '', fileType = 'all') {
        try {
            this.showLoading();
            
            const params = new URLSearchParams({
                page: page.toString(),
                limit: '50'
            });
            
            if (search) params.append('search', search);
            if (fileType !== 'all') params.append('file_type', fileType);
            
            const response = await fetch(`/admin/api/files?${params}`);
            const data = await response.json();
            
            this.renderFilesTable(data.files);
            this.renderPagination('files', data.pagination);
            
            this.hideLoading();
        } catch (error) {
            console.error('Failed to load files:', error);
            this.showError('Failed to load files');
            this.hideLoading();
        }
    }

    async loadUsers(page = 1, search = '', statusFilter = 'all') {
        try {
            this.showLoading();
            
            const params = new URLSearchParams({
                page: page.toString(),
                limit: '50'
            });
            
            if (search) params.append('search', search);
            if (statusFilter !== 'all') params.append('status_filter', statusFilter);
            
            const response = await fetch(`/admin/api/users?${params}`);
            const data = await response.json();
            
            this.renderUsersGrid(data.users);
            
            this.hideLoading();
        } catch (error) {
            console.error('Failed to load users:', error);
            this.showError('Failed to load users');
            this.hideLoading();
        }
    }

    async loadAnalytics() {
        try {
            this.showLoading();
            
            const response = await fetch('/admin/api/analytics?period=30');
            const data = await response.json();
            
            if (data.error) {
                this.showError('Analytics are disabled');
                this.hideLoading();
                return;
            }
            
            this.updateAnalyticsCharts(data);
            
            this.hideLoading();
        } catch (error) {
            console.error('Failed to load analytics:', error);
            this.showError('Failed to load analytics');
            this.hideLoading();
        }
    }

    async loadLogs(page = 1, actionFilter = 'all') {
        try {
            this.showLoading();
            
            const params = new URLSearchParams({
                page: page.toString(),
                limit: '100'
            });
            
            if (actionFilter !== 'all') params.append('action_filter', actionFilter);
            
            const response = await fetch(`/admin/api/logs?${params}`);
            const data = await response.json();
            
            this.renderLogs(data.logs);
            
            this.hideLoading();
        } catch (error) {
            console.error('Failed to load logs:', error);
            this.showError('Failed to load logs');
            this.hideLoading();
        }
    }

    renderFilesTable(files) {
        const tbody = document.getElementById('filesTableBody');
        if (!tbody) return;
        
        tbody.innerHTML = files.map(file => `
            <tr data-file-id="${file.file_id}">
                <td><input type="checkbox" class="file-checkbox" value="${file.file_id}"></td>
                <td>
                    <div class="file-info">
                        <span class="file-icon">${this.getFileIcon(file.file_extension)}</span>
                        <span class="file-name" title="${file.file_name}">${this.truncateText(file.file_name, 30)}</span>
                    </div>
                </td>
                <td>${this.formatFileSize(file.file_size)}</td>
                <td>${file.file_extension.toUpperCase() || 'Unknown'}</td>
                <td>
                    <div class="user-info">
                        <span class="user-name">${file.uploader_username || 'Unknown'}</span>
                        <small class="user-id">ID: ${file.uploader_id}</small>
                    </div>
                </td>
                <td>${this.formatDate(file.upload_time)}</td>
                <td>
                    <span class="download-count">${file.download_count.toLocaleString()}</span>
                </td>
                <td>
                    <div class="file-actions">
                        <button class="action-btn-sm primary" onclick="adminDashboard.viewFile('${file.unique_code}')" title="View">
                            <i data-feather="eye"></i>
                        </button>
                        <button class="action-btn-sm warning" onclick="adminDashboard.downloadFile('${file.file_id}', '${file.unique_code}')" title="Download">
                            <i data-feather="download"></i>
                        </button>
                        <button class="action-btn-sm danger" onclick="adminDashboard.deleteFile('${file.file_id}')" title="Delete">
                            <i data-feather="trash-2"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
        
        // Re-initialize Feather icons
        feather.replace();
    }

    renderUsersGrid(users) {
        const grid = document.getElementById('usersGrid');
        if (!grid) return;
        
        grid.innerHTML = users.map(user => `
            <div class="user-card ${user.is_blocked ? 'blocked' : ''}" data-user-id="${user.user_id}">
                <div class="user-avatar">
                    ${user.first_name ? user.first_name[0].toUpperCase() : '?'}
                </div>
                <div class="user-details">
                    <div class="user-name">
                        ${user.first_name} ${user.last_name || ''}
                        ${user.is_blocked ? '<span class="user-status blocked">Blocked</span>' : '<span class="user-status active">Active</span>'}
                    </div>
                    <div class="user-username">@${user.username || 'N/A'}</div>
                    <div class="user-stats">
                        <div class="stat">
                            <i data-feather="file"></i>
                            <span>${user.total_uploads} files</span>
                        </div>
                        <div class="stat">
                            <i data-feather="calendar"></i>
                            <span>Joined ${this.formatDate(user.join_date)}</span>
                        </div>
                        <div class="stat">
                            <i data-feather="activity"></i>
                            <span>Active ${this.timeAgo(user.last_activity)}</span>
                        </div>
                    </div>
                    <div class="user-actions">
                        ${user.is_blocked 
                            ? `<button class="action-btn-sm success" onclick="adminDashboard.unblockUser(${user.user_id})">
                                <i data-feather="unlock"></i> Unblock
                            </button>`
                            : `<button class="action-btn-sm danger" onclick="adminDashboard.blockUser(${user.user_id})">
                                <i data-feather="lock"></i> Block
                            </button>`
                        }
                        <button class="action-btn-sm primary" onclick="adminDashboard.viewUserFiles(${user.user_id})">
                            <i data-feather="folder"></i> Files
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
        
        // Re-initialize Feather icons
        feather.replace();
    }

    renderLogs(logs) {
        const container = document.getElementById('logsContainer');
        if (!container) return;
        
        container.innerHTML = logs.map(log => `
            <div class="log-entry ${log.action}">
                <div class="log-icon">
                    ${this.getLogIcon(log.action)}
                </div>
                <div class="log-content">
                    <div class="log-action">${this.formatLogAction(log.action)}</div>
                    <div class="log-details">${this.formatLogDetails(log.details)}</div>
                    <div class="log-timestamp">${this.formatDate(log.timestamp)}</div>
                </div>
            </div>
        `).join('');
    }

    async deleteFile(fileId) {
        if (!confirm('Are you sure you want to delete this file? This action cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch(`/admin/api/files/${fileId}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('File deleted successfully');
                this.loadFiles(); // Refresh the list
            } else {
                this.showError('Failed to delete file');
            }
        } catch (error) {
            console.error('Delete file error:', error);
            this.showError('Failed to delete file');
        }
    }

    async blockUser(userId) {
        if (!confirm('Are you sure you want to block this user?')) {
            return;
        }
        
        try {
            const response = await fetch(`/admin/api/users/${userId}/block`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('User blocked successfully');
                this.loadUsers(); // Refresh the list
            } else {
                this.showError('Failed to block user');
            }
        } catch (error) {
            console.error('Block user error:', error);
            this.showError('Failed to block user');
        }
    }

    async unblockUser(userId) {
        try {
            const response = await fetch(`/admin/api/users/${userId}/unblock`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('User unblocked successfully');
                this.loadUsers(); // Refresh the list
            } else {
                this.showError('Failed to unblock user');
            }
        } catch (error) {
            console.error('Unblock user error:', error);
            this.showError('Failed to unblock user');
        }
    }

    initializeCharts() {
        // Initialize Chart.js charts
        this.initUploadChart();
        this.initDownloadChart();
    }

    initUploadChart() {
        const ctx = document.getElementById('uploadsChart');
        if (!ctx) return;
        
        this.charts.uploads = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Uploads',
                    data: [],
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#a0a0db'
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#a0a0db'
                        }
                    }
                }
            }
        });
    }

    initDownloadChart() {
        const ctx = document.getElementById('downloadsChart');
        if (!ctx) return;
        
        this.charts.downloads = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Downloads',
                    data: [],
                    backgroundColor: '#51cf66',
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#a0a0db'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#a0a0db'
                        }
                    }
                }
            }
        });
    }

    updateUploadChart(stats) {
        if (!this.charts.uploads || !stats.upload_trends) return;
        
        const labels = stats.upload_trends.map(item => item.date);
        const data = stats.upload_trends.map(item => item.uploads);
        
        this.charts.uploads.data.labels = labels;
        this.charts.uploads.data.datasets[0].data = data;
        this.charts.uploads.update();
    }

    updateDownloadChart(stats) {
        if (!this.charts.downloads || !stats.download_stats?.daily_stats) return;
        
        const labels = stats.download_stats.daily_stats.map(item => item._id);
        const data = stats.download_stats.daily_stats.map(item => item.count);
        
        this.charts.downloads.data.labels = labels;
        this.charts.downloads.data.datasets[0].data = data;
        this.charts.downloads.update();
    }

    // Utility functions
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    formatDate(timestamp) {
        const date = new Date(timestamp * 1000);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }

    timeAgo(timestamp) {
        const now = Date.now() / 1000;
        const diff = now - timestamp;
        
        if (diff < 60) return 'just now';
        if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
        if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
        return Math.floor(diff / 86400) + 'd ago';
    }

    truncateText(text, length) {
        return text.length > length ? text.substring(0, length) + '...' : text;
    }

    getFileIcon(extension) {
        const iconMap = {
            jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️',
            mp4: '🎥', avi: '🎥', mov: '🎥', mkv: '🎥',
            mp3: '🎵', wav: '🎵', ogg: '🎵',
            pdf: '📕', doc: '📘', docx: '📘', txt: '📝',
            zip: '🗜️', rar: '🗜️', '7z': '🗜️'
        };
        return iconMap[extension?.toLowerCase()] || '📄';
    }

    getLogIcon(action) {
        const iconMap = {
            file_upload: '📁',
            file_delete: '🗑️',
            user_block: '🚫',
            user_unblock: '✅',
            settings_change: '⚙️',
            broadcast_message: '📢'
        };
        return iconMap[action] || '📝';
    }

    formatLogAction(action) {
        const actionMap = {
            file_upload: 'File Uploaded',
            file_delete: 'File Deleted',
            user_block: 'User Blocked',
            user_unblock: 'User Unblocked',
            settings_change: 'Settings Changed',
            broadcast_message: 'Message Broadcasted'
        };
        return actionMap[action] || action;
    }

    formatLogDetails(details) {
        if (details.file_name) return `File: ${details.file_name}`;
        if (details.user_id) return `User ID: ${details.user_id}`;
        return JSON.stringify(details);
    }

    showLoading() {
        document.getElementById('loadingOverlay')?.classList.add('active');
    }

    hideLoading() {
        document.getElementById('loadingOverlay')?.classList.remove('active');
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showError(message) {
        this.showToast(message, 'error');
    }

    showToast(message, type) {
        // Create toast notification
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    closeModal() {
        document.getElementById('modalOverlay')?.classList.remove('active');
    }

    refreshCurrentSection() {
        this.loadSectionData(this.currentSection);
    }

    startAutoRefresh() {
        // Refresh dashboard data every 30 seconds
        this.refreshInterval = setInterval(() => {
            if (this.currentSection === 'dashboard') {
                this.loadDashboardData();
            }
        }, 30000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}

// Initialize the dashboard
let adminDashboard;
document.addEventListener('DOMContentLoaded', () => {
    adminDashboard = new AdminDashboard();
});

// Global functions
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        window.location.href = '/admin/logout';
    }
}