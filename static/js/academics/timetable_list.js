// JavaScript for timetable_list.html
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchTimetable');
    const timetableTableBody = document.getElementById('timetableTableBody');

    if (searchInput && timetableTableBody) {
        searchInput.addEventListener('keyup', function() {
            const filter = searchInput.value.toLowerCase();
            const rows = timetableTableBody.getElementsByTagName('tr');

            for (let i = 0; i < rows.length; i++) {
                let row = rows[i];
                let cells = row.getElementsByTagName('td');
                let found = false;
                for (let j = 0; j < cells.length; j++) {
                    let cell = cells[j];
                    if (cell) {
                        if (cell.textContent.toLowerCase().indexOf(filter) > -1) {
                            found = true;
                            break;
                        }
                    }
                }
                if (found) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            }
        });
    }

    // Add any other specific JS for timetable list here
});
