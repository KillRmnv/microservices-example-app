const Auth = {
    TOKEN_KEY: 'token',
    USER_EMAIL_KEY: 'userEmail',
    USER_ROLE_KEY: 'userRole',

    getToken() {
        return localStorage.getItem(this.TOKEN_KEY);
    },

    getUserEmail() {
        return localStorage.getItem(this.USER_EMAIL_KEY);
    },

    getUserRole() {
        return localStorage.getItem(this.USER_ROLE_KEY);
    },

    isLoggedIn() {
        return !!this.getToken();
    },

    setSession(token, email, role) {
        localStorage.setItem(this.TOKEN_KEY, token);
        localStorage.setItem(this.USER_EMAIL_KEY, email);
        localStorage.setItem(this.USER_ROLE_KEY, role);
    },

    clearSession() {
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.USER_EMAIL_KEY);
        localStorage.removeItem(this.USER_ROLE_KEY);
    },

    async login(email, password) {
        const response = await API.login(email, password);
        if (response.token) {
            this.setSession(response.token, email, response.role || 'CUSTOMER');
            return response;
        }
        throw new Error('No token received');
    },

    async register(email, password, username, role = 'CUSTOMER') {
        return API.register(email, password, username, role);
    },

    logout() {
        this.clearSession();
        window.location.hash = '#/';
        location.reload();
    },

    isAdmin() {
        return this.getUserRole() === 'ADMIN';
    },

    isEventManager() {
        return this.getUserRole() === 'EVENT_MANAGER';
    },

    isCustomer() {
        return this.getUserRole() === 'CUSTOMER';
    },

    canManageEvents() {
        const role = this.getUserRole();
        return role === 'ADMIN' || role === 'EVENT_MANAGER';
    },

    canManageUsers() {
        return this.getUserRole() === 'ADMIN';
    },

    canManageInfrastructure() {
        return this.getUserRole() === 'ADMIN';
    }
};