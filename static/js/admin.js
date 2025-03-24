document.addEventListener('DOMContentLoaded', function() {
    // Check if we have a valid session
    const token = sessionStorage.getItem('adminToken');
    if (!token) {
        window.location.href = '/';
        return;
    }

    // Add authorization header to all fetch requests
    const headers = {
        'Authorization': `Bearer ${token}`
    };

    // Fetch admin stats
    fetchAdminStats();

    // Handle logout
    document.getElementById('logoutBtn').addEventListener('click', () => {
        sessionStorage.removeItem('adminToken');
        window.location.href = '/';
    });

    // Handle CSV download
    document.getElementById('downloadCSVBtn').addEventListener('click', () => {
        downloadDatabaseCSV(token);
    });
});

async function fetchAdminStats() {
    try {
        const token = sessionStorage.getItem('adminToken');
        const response = await fetch('/admin/stats', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            if (response.status === 401) {
                // Unauthorized - redirect to home page
                window.location.href = '/';
                return;
            }
            throw new Error('Failed to fetch admin stats');
        }

        const data = await response.json();
        
        // Update stats
        document.getElementById('adminTotalInterest').textContent = data.total_interest;
        document.getElementById('adminUniqueVisitors').textContent = data.unique_visitors;
        document.getElementById('adminTotalSubscribers').textContent = data.total_subscribers;
        
        // Update recent interest
        const recentInterestDiv = document.getElementById('adminRecentInterest');
        recentInterestDiv.innerHTML = data.recent_interest.map(item => `
            <div class="admin-recent-item">
                <span class="admin-recent-value">${item[0]}</span>
                <span class="admin-recent-timestamp">${new Date(item[1]).toLocaleString()}</span>
            </div>
        `).join('');
        
        // Update recent subscribers
        const recentSubscribersDiv = document.getElementById('adminRecentSubscribers');
        recentSubscribersDiv.innerHTML = data.recent_subscribers.map(item => `
            <div class="admin-recent-item">
                <span class="admin-recent-value">${item[0]}</span>
                <span class="admin-recent-timestamp">${new Date(item[1]).toLocaleString()}</span>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error fetching admin stats:', error);
        if (error.message === 'Unauthorized') {
            window.location.href = '/';
        }
    }
}

async function downloadDatabaseCSV(token) {
    try {
        const response = await fetch(`/export-data?password=${encodeURIComponent(token)}`);
        if (!response.ok) {
            if (response.status === 401) {
                // Unauthorized - redirect to home page
                window.location.href = '/';
                return;
            }
            throw new Error('Failed to fetch data');
        }
        
        const data = await response.json();
        
        // Create CSV content
        let csvContent = "data:text/csv;charset=utf-8,";
        
        // Add summary section
        csvContent += "Summary\n";
        csvContent += "Total Interest,Unique Visitors,Total Subscribers\n";
        csvContent += `${data.summary.total_interest},${data.summary.unique_visitors},${data.summary.total_subscribers}\n\n`;
        
        // Add interest data
        csvContent += "Interest Data\n";
        csvContent += "IP Address,Timestamp\n";
        data.interest_data.forEach(item => {
            const cleanIP = item.ip_address.replace(/"/g, '""');
            const cleanTimestamp = item.timestamp.replace(/"/g, '""');
            csvContent += `"${cleanIP}","${cleanTimestamp}"\n`;
        });
        
        // Add email subscribers
        csvContent += "\nEmail Subscribers\n";
        csvContent += "Email,Timestamp\n";
        data.email_data.forEach(item => {
            const cleanEmail = item.email.replace(/"/g, '""');
            const cleanTimestamp = item.timestamp.replace(/"/g, '""');
            csvContent += `"${cleanEmail}","${cleanTimestamp}"\n`;
        });
        
        // Create download link
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `database_export_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } catch (error) {
        console.error('Error downloading database:', error);
        alert('Failed to download database. Please try again.');
    }
} 