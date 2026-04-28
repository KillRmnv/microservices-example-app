const API = {
    baseUrl: 'http://localhost:8080',

    async request(endpoint, options = {}) {
        const token = localStorage.getItem('token');
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                ...options,
                headers
            });

            const data = await response.json().catch(() => null);

            if (!response.ok) {
                throw new Error(data?.message || `HTTP ${response.status}`);
            }

            return data;
        } catch (error) {
            throw error;
        }
    },

    get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    },

    post(endpoint, body) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(body)
        });
    },

    put(endpoint, body) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(body)
        });
    },

    delete(endpoint, body) {
        return this.request(endpoint, {
            method: 'DELETE',
            body: body ? JSON.stringify(body) : undefined
        });
    },

    async getUserById(id) {
        return this.get(`/users/${id}`);
    },

    async getMyTickets(userId) {
        const tickets = await this.searchTickets({ userId });
        const seatableTickets = await this.searchSeatableTickets({ userId });
        return { tickets, seatableTickets };
    },

    async searchTickets(filter, page = 1, size = 100) {
        const params = new URLSearchParams();
        if (filter.eventId) params.append('eventId', filter.eventId);
        if (filter.userId) params.append('userId', filter.userId);
        if (filter.zone) params.append('zone', filter.zone);
        if (filter.active !== undefined) params.append('active', filter.active);
        if (filter.minPrice) params.append('minPrice', filter.minPrice);
        if (filter.maxPrice) params.append('maxPrice', filter.maxPrice);
        params.append('page', page);
        params.append('size', size);
        return this.get(`/booking/tickets/search?${params}`);
    },

    async searchSeatableTickets(filter, page = 1, size = 100) {
        const params = new URLSearchParams();
        if (filter.eventId) params.append('eventId', filter.eventId);
        if (filter.userId) params.append('userId', filter.userId);
        if (filter.zone) params.append('zone', filter.zone);
        if (filter.active !== undefined) params.append('active', filter.active);
        if (filter.minPrice) params.append('minPrice', filter.minPrice);
        if (filter.maxPrice) params.append('maxPrice', filter.maxPrice);
        if (filter.sector) params.append('sector', filter.sector);
        if (filter.row) params.append('row', filter.row);
        if (filter.number) params.append('number', filter.number);
        params.append('page', page);
        params.append('size', size);
        return this.get(`/booking/seatable-tickets/search?${params}`);
    },

    async login(email, password) {
        console.log('[API] Login request for:', email);
        const response = await this.post('/users/auth/login', { email, password });
        console.log('[API] Login response:', response);
        return response;
    },

    async register(email, password, username, role = 'CUSTOMER') {
        return this.post('/users/auth/register', { email, password, username, role });
    },

    async forgetPassword(email) {
        return this.get(`/users/auth/forget-password?email=${encodeURIComponent(email)}`);
    },

    async resetPassword(token, newPassword) {
        return this.post(`/users/auth/reset-password?token=${encodeURIComponent(token)}&newPassword=${encodeURIComponent(newPassword)}`);
    },

    async getRoles() {
        return this.get('/users/auth/roles');
    },

    async validateResetToken(token) {
        return this.get(`/users/auth/validate-reset-token?token=${encodeURIComponent(token)}`);
    },

    async getCurrentUser() {
        return this.get('/users/by-email?email=' + encodeURIComponent(localStorage.getItem('userEmail')));
    },

    async getAllUsers() {
        return this.get('/users');
    },

    async getUsersByPage(page, size) {
        return this.get(`/users/page?page=${page}&size=${size}`);
    },

    async searchUsers(filter) {
        const params = new URLSearchParams();
        if (filter.email) params.append('email', filter.email);
        if (filter.username) params.append('username', filter.username);
        if (filter.role) params.append('role', filter.role);
        return this.get(`/users/search?${params}`);
    },

    async updateUser(data) {
        return this.put('/users', data);
    },

    async deleteUser(id) {
        return this.delete('/users', { id });
    },

    async getEvents() {
        return this.get('/booking/events');
    },

    async getEventById(id) {
        return this.get(`/booking/events/${id}`);
    },

    async searchEvents(filter, page = 1, size = 10) {
        const params = new URLSearchParams();
        if (filter.title) params.append('title', filter.title);
        if (filter.venueId) params.append('venueId', filter.venueId);
        if (filter.admissionMode) params.append('admissionMode', filter.admissionMode);
        if (filter.startsFrom) params.append('startsFrom', filter.startsFrom);
        if (filter.startsTo) params.append('startsTo', filter.startsTo);
        params.append('page', page);
        params.append('size', size);
        return this.get(`/booking/events/search?${params}`);
    },

    async createEvent(data) {
        return this.post('/booking/events', data);
    },

    async updateEvent(data) {
        return this.put(`/booking/events/${data.id}`, data);
    },

    async deleteEvent(id) {
        return this.delete(`/booking/events/${id}`);
    },

    async deleteEventsByFilter(filter) {
        return this.delete('/booking/events/search', filter);
    },

    async getTowns() {
        return this.get('/booking/towns');
    },

    async getTownById(id) {
        return this.get(`/booking/towns/${id}`);
    },

    async createTown(data) {
        return this.post('/booking/towns', data);
    },

    async deleteTown(id) {
        return this.delete(`/booking/towns/${id}`);
    },

    async getVenues() {
        return this.get('/booking/venues');
    },

    async getVenueById(id) {
        return this.get(`/booking/venues/${id}`);
    },

    async searchVenues(filter, page = 1, size = 10) {
        const params = new URLSearchParams();
        if (filter.townId) params.append('townId', filter.townId);
        if (filter.place) params.append('place', filter.place);
        params.append('page', page);
        params.append('size', size);
        return this.get(`/booking/venues/search?${params}`);
    },

    async createVenue(data) {
        return this.post('/booking/venues', data);
    },

    async updateVenue(data) {
        return this.put(`/booking/venues/${data.id}`, data);
    },

    async deleteVenue(id) {
        return this.delete(`/booking/venues/${id}`);
    },

    async getSeats(filter, page = 1, size = 100) {
        const params = new URLSearchParams();
        if (filter.venueId) params.append('venueId', filter.venueId);
        params.append('page', page);
        params.append('size', size);
        return this.get(`/booking/seats/search?${params}`);
    },

    async createSeat(data) {
        return this.post('/booking/seats', data);
    },

    async updateSeat(data) {
        return this.put(`/booking/seats/${data.id}`, data);
    },

    async deleteSeat(id) {
        return this.delete(`/booking/seats/${id}`);
    },

    async getTickets(eventId) {
        return this.get(`/booking/tickets/search?eventId=${eventId}&page=1&size=100`);
    },

    async getSeatableTickets(eventId) {
        return this.get(`/booking/seatable-tickets/search?eventId=${eventId}&page=1&size=100`);
    },

    async createTicket(data) {
        return this.post('/booking/tickets', data);
    },

    async createSeatableTicket(data) {
        return this.post('/booking/seatable-tickets', data);
    },

    async deleteTicket(id) {
        return this.delete(`/booking/tickets/${id}`);
    },

    async deleteSeatableTicket(id) {
        return this.delete(`/booking/seatable-tickets/${id}`);
    }
};

// Make API globally accessible
window.API = API;