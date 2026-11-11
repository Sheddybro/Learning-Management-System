// JavaScript for teacher_timetable.html
document.addEventListener('DOMContentLoaded', function() {
    const sessionSelect = document.getElementById('sessionSelect');
    const termSelect = document.getElementById('termSelect');

    function loadTimetable() {
        const sessionId = sessionSelect ? sessionSelect.value : null;
        const termId = termSelect ? termSelect.value : null;

        if (sessionId && termId) {
            // In a real application, you would make an AJAX request here
            // to fetch timetable data based on selected session and term.
            console.log(`Loading timetable for session ID: ${sessionId}, term ID: ${termId}`);
            // Example: fetch(`/api/teacher-timetable/?session=${sessionId}&term=${termId}`)
            // .then(response => response.json())
            // .then(data => {
            //     // Update the timetable-grid with new data
            //     console.log('Timetable data received:', data);
            // })
            // .catch(error => console.error('Error loading timetable:', error));
        }
    }

    if (sessionSelect) {
        sessionSelect.addEventListener('change', loadTimetable);
    }
    if (termSelect) {
        termSelect.addEventListener('change', loadTimetable);
    }

    // Initial load if elements exist
    if (sessionSelect || termSelect) {
        loadTimetable();
    }

    // Add any other specific JS for teacher timetable here
});
