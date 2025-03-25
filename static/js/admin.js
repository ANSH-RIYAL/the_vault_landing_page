document.addEventListener('DOMContentLoaded', function() {
    // Get the password from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const password = urlParams.get('password');
    
    if (!password) {
        window.location.href = '/';
        return;
    }

    // Fetch admin stats with password
    fetch('/admin/stats?password=' + encodeURIComponent(password))
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Update total interest
            document.getElementById('totalInterest').textContent = data.total_interest;
            
            // Update total subscribers
            document.getElementById('totalSubscribers').textContent = data.total_subscribers;
            
            // Update recent interest
            const recentInterestHtml = data.recent_interest.map(item => `
                <div class="glass-effect rounded-lg p-3 flex justify-between items-center">
                    <span class="text-nyu-purple">Interest recorded</span>
                    <span class="text-gray-600 text-sm">${formatDate(item.timestamp)}</span>
                </div>
            `).join('');
            document.getElementById('recentInterest').innerHTML = recentInterestHtml || 'No recent interest';
            
            // Update recent subscribers
            const recentSubscribersHtml = data.recent_subscribers.map(item => `
                <div class="glass-effect rounded-lg p-3 flex justify-between items-center">
                    <span class="text-nyu-purple">${item.email}</span>
                    <span class="text-gray-600 text-sm">${formatDate(item.timestamp)}</span>
                </div>
            `).join('');
            document.getElementById('recentSubscribers').innerHTML = recentSubscribersHtml || 'No recent subscribers';
        })
        .catch(error => {
            console.error('Error fetching admin stats:', error);
            document.getElementById('totalInterest').textContent = 'Error';
            document.getElementById('totalSubscribers').textContent = 'Error';
            document.getElementById('recentInterest').innerHTML = 'Error loading data';
            document.getElementById('recentSubscribers').innerHTML = 'Error loading data';
        });

    // Handle logout
    document.getElementById('logoutBtn')?.addEventListener('click', () => {
        window.location.href = '/';
    });

    // Handle CSV download
    document.getElementById('downloadCSVBtn')?.addEventListener('click', () => {
        downloadDatabaseCSV(password);
    });
});

// Utility functions
function formatDate(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });
}

// Export CSV
async function exportCSV() {
    try {
        const adminToken = localStorage.getItem('adminToken');
        if (!adminToken) {
            throw new Error('No admin token found');
        }

        const response = await fetch('/admin/export', {
            headers: {
                'Authorization': `Bearer ${adminToken}`
            }
        });

        if (!response.ok) {
            if (response.status === 401) {
                window.location.href = '/';
                return;
            }
            throw new Error('Failed to export data');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'admin_data.csv';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        console.error('Error exporting data:', error);
        if (error.message === 'No admin token found') {
            window.location.href = '/';
        }
    }
}

// Download database as CSV
async function downloadDatabaseCSV(password) {
    try {
        const response = await fetch(`/admin/download-csv?password=${encodeURIComponent(password)}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // Get the filename from the Content-Disposition header
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'admin_stats.csv';
        if (contentDisposition) {
            const matches = /filename="(.+)"/.exec(contentDisposition);
            if (matches) {
                filename = matches[1];
            }
        }
        
        // Create a blob from the response
        const blob = await response.blob();
        
        // Create a link element and trigger download
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        console.error('Error downloading CSV:', error);
        alert('Failed to download CSV file. Please try again.');
    }
}

// Fetch admin stats
async function fetchAdminStats() {
    try {
        const response = await fetch('/admin/stats?password=isha');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        updateAdminStats(data);
    } catch (error) {
        console.error('Error fetching admin stats:', error);
        document.getElementById('totalInterest').textContent = 'Error loading data';
        document.getElementById('totalSubscribers').textContent = 'Error loading data';
        document.getElementById('recentInterest').innerHTML = 'Error loading data';
        document.getElementById('recentSubscribers').innerHTML = 'Error loading data';
    }
} 