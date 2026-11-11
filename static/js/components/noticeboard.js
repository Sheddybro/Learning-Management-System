document.addEventListener('DOMContentLoaded', function() {
    let currentBannerIndex = 0;
    const bannerAnnouncements = window.bannerAnnouncements || 0;
    const bannerContainer = document.querySelector('.noticeboard-marquee');
    const currentBannerDisplay = document.getElementById('current-banner');

    function rotateNotification(direction) {
        if (!bannerContainer) return;

        const announcements = bannerContainer.querySelectorAll('.noticeboard-announcement');

        // Hide current announcement
        announcements[currentBannerIndex].classList.add('d-none');

        // Calculate new index
        currentBannerIndex = (currentBannerIndex + direction + bannerAnnouncements) % bannerAnnouncements;

        // Show new announcement
        announcements[currentBannerIndex].classList.remove('d-none');

        // Update counter
        if (currentBannerDisplay) {
            currentBannerDisplay.textContent = currentBannerIndex + 1;
        }
    }

    function hideNoticeboardBanner() {
        const banner = document.getElementById('noticeboard-banner');
        if (banner) {
            banner.style.display = 'none';
            // Store preference to hide banner for this session
            sessionStorage.setItem('noticeboard-banner-hidden', 'true');
        }
    }

    // Auto-rotate banners every 30 seconds
    setInterval(() => {
        if (!sessionStorage.getItem('noticeboard-banner-hidden')) {
            rotateNotification(1);
        }
    }, 30000);

    // Check if banner should be hidden on page load
    if (sessionStorage.getItem('noticeboard-banner-hidden')) {
        hideNoticeboardBanner();
    }

    // Make functions globally available for onclick handlers
    window.rotateNotification = rotateNotification;
    window.hideNoticeboardBanner = hideNoticeboardBanner;
});
