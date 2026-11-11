// static/js/academics/calendar.js

class AcademicCalendar {
    constructor(config) {
        this.config = config;
        this.currentDate = new Date();
        this.currentView = 'month';
        this.calendarElement = document.getElementById('calendar-days');
        this.monthYearElement = document.getElementById('current-month-year');
    }

    init() {
        this.setupEventListeners();
        this.renderMonthView();
    }

    setupEventListeners() {
        // View toggle
        document.getElementById('month-view').addEventListener('click', () => this.switchView('month'));
        document.getElementById('list-view').addEventListener('click', () => this.switchView('list'));

        // Month navigation
        document.getElementById('prev-month').addEventListener('click', () => this.previousMonth());
        document.getElementById('next-month').addEventListener('click', () => this.nextMonth());
        document.getElementById('current-month').addEventListener('click', () => this.goToToday());

        // Holiday modal
        const holidayModal = document.getElementById('holidayModal');
        if (holidayModal) {
            holidayModal.addEventListener('show.bs.modal', (event) => {
                const button = event.relatedTarget;
                const holidayId = button.getAttribute('data-holiday-id');
                this.showHolidayDetails(holidayId);
            });
        }
    }

    switchView(view) {
        this.currentView = view;
        
        // Update button states
        document.getElementById('month-view').classList.toggle('active', view === 'month');
        document.getElementById('list-view').classList.toggle('active', view === 'list');
        
        // Show/hide views
        document.getElementById('month-view-content').classList.toggle('d-none', view !== 'month');
        document.getElementById('list-view-content').classList.toggle('d-none', view !== 'list');
    }

    previousMonth() {
        this.currentDate.setMonth(this.currentDate.getMonth() - 1);
        this.renderMonthView();
    }

    nextMonth() {
        this.currentDate.setMonth(this.currentDate.getMonth() + 1);
        this.renderMonthView();
    }

    goToToday() {
        this.currentDate = new Date();
        this.renderMonthView();
    }

    renderMonthView() {
        const year = this.currentDate.getFullYear();
        const month = this.currentDate.getMonth();
        
        this.monthYearElement.textContent = this.currentDate.toLocaleDateString(
            this.config.currentLanguage || 'en', 
            { month: 'long', year: 'numeric' }
        );

        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const startingDay = firstDay.getDay();
        const monthLength = lastDay.getDate();

        let calendarHTML = '';
        let date = 1;

        // Create calendar grid
        for (let i = 0; i < 6; i++) {
            for (let j = 0; j < 7; j++) {
                if (i === 0 && j < startingDay) {
                    // Previous month days
                    const prevDate = new Date(year, month, 0 - (startingDay - j - 1));
                    calendarHTML += this.createDayElement(prevDate, true);
                } else if (date > monthLength) {
                    // Next month days
                    const nextDate = new Date(year, month + 1, date - monthLength);
                    calendarHTML += this.createDayElement(nextDate, true);
                    date++;
                } else {
                    // Current month days
                    const currentDate = new Date(year, month, date);
                    calendarHTML += this.createDayElement(currentDate, false);
                    date++;
                }
            }
        }

        this.calendarElement.innerHTML = calendarHTML;
        this.attachDayEventListeners();
    }

    createDayElement(date, isOtherMonth) {
        const dayNumber = date.getDate();
        const dateString = date.toISOString().split('T')[0];
        const isToday = dateString === this.config.today;
        const isWeekend = date.getDay() === 0 || date.getDay() === 6;
        const isHoliday = this.isHoliday(dateString);
        const isSessionDay = this.isSessionDay(dateString);

        let dayClass = 'calendar-day';
        if (isOtherMonth) dayClass += ' other-month';
        if (isWeekend) dayClass += ' weekend';
        if (isToday) dayClass += ' today';
        if (isHoliday) dayClass += ' holiday';
        if (isSessionDay) dayClass += ' session-day';

        const events = this.getDayEvents(dateString);
        const eventsHTML = events.map(event => 
            `<div class="calendar-event ${event.type}" 
                  data-bs-toggle="modal" 
                  data-bs-target="#holidayModal"
                  data-holiday-id="${event.id}">
                ${event.name}
            </div>`
        ).join('');

        return `
            <div class="${dayClass}" data-date="${dateString}">
                <div class="calendar-day-number">${dayNumber}</div>
                <div class="calendar-events">${eventsHTML}</div>
            </div>
        `;
    }

    isHoliday(dateString) {
        return this.config.holidays.some(holiday => holiday.date === dateString);
    }

    isSessionDay(dateString) {
        const date = new Date(dateString);
        const startDate = new Date(this.config.currentSession.startDate);
        const endDate = new Date(this.config.currentSession.endDate);
        return date >= startDate && date <= endDate;
    }

    getDayEvents(dateString) {
        return this.config.holidays
            .filter(holiday => holiday.date === dateString)
            .map(holiday => ({
                id: holiday.id,
                name: holiday.name,
                type: 'holiday'
            }));
    }

    attachDayEventListeners() {
        const dayElements = this.calendarElement.querySelectorAll('.calendar-day');
        dayElements.forEach(day => {
            day.addEventListener('click', (e) => {
                if (!e.target.closest('.calendar-event')) {
                    this.showDayDetails(day.getAttribute('data-date'));
                }
            });
        });
    }

    showDayDetails(dateString) {
        const date = new Date(dateString);
        const events = this.getDayEvents(dateString);
        
        let message = `<strong>${date.toLocaleDateString(this.config.currentLanguage || 'en', { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        })}</strong>`;
        
        if (events.length > 0) {
            message += `<div class="mt-2"><strong>${this.config.texts.holiday}:</strong> ${events[0].name}</div>`;
        } else {
            message += `<div class="mt-2 text-muted">${this.config.texts.noEvents}</div>`;
        }

        // You could implement a custom modal or use browser alert for simplicity
        alert(message);
    }

    showHolidayDetails(holidayId) {
        const holiday = this.config.holidays.find(h => h.id == holidayId);
        if (!holiday) return;

        const modalBody = document.getElementById('holidayModalBody');
        const modalTitle = document.getElementById('holidayModalLabel');
        
        modalTitle.textContent = holiday.name;
        
        const date = new Date(holiday.date);
        modalBody.innerHTML = `
            <div class="holiday-details">
                <p><strong>${this.config.texts.holiday}:</strong> ${holiday.name}</p>
                <p><strong>${this.config.texts.date}:</strong> ${date.toLocaleDateString(this.config.currentLanguage || 'en', { 
                    weekday: 'long', 
                    year: 'numeric', 
                    month: 'long', 
                    day: 'numeric' 
                })}</p>
                ${holiday.description ? `<p><strong>${this.config.texts.description}:</strong> ${holiday.description}</p>` : ''}
                <p><strong>${this.config.texts.type}:</strong> ${holiday.isRecurring ? 
                    this.config.texts.recurring : this.config.texts.oneTime}</p>
            </div>
        `;
    }
}