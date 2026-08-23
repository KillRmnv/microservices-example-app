// API is available from global scope (set by api.js)

const Auth = {
    TOKEN_KEY: 'token',
    USER_EMAIL_KEY: 'userEmail',
    USER_ROLE_KEY: 'userRole',
    USER_ID_KEY: 'userId',

    getToken() {
        return localStorage.getItem(this.TOKEN_KEY);
    },

    getUserEmail() {
        return localStorage.getItem(this.USER_EMAIL_KEY);
    },

    getUserRole() {
        return localStorage.getItem(this.USER_ROLE_KEY);
    },

    getUserId() {
        return localStorage.getItem(this.USER_ID_KEY);
    },

    isLoggedIn() {
        const token = this.getToken();
        if (!token) return false;
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            return payload.exp * 1000 > Date.now();
        } catch {
            return false;
        }
    },

    setSession(token, email, role, userId) {
        localStorage.setItem(this.TOKEN_KEY, token);
        localStorage.setItem(this.USER_EMAIL_KEY, email);
        localStorage.setItem(this.USER_ROLE_KEY, role);
        if (userId) localStorage.setItem(this.USER_ID_KEY, userId);
    },

    clearSession() {
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.USER_EMAIL_KEY);
        localStorage.removeItem(this.USER_ROLE_KEY);
        localStorage.removeItem(this.USER_ID_KEY);
    },

    async login(email, password) {
        const response = await API.login(email, password);
        
        if (response.jwt) {
            const role = response.role || 'CUSTOMER';
            this.setSession(response.jwt, email, role, response.id);
            return response;
        }
        throw new Error('No token received');
    },

    async updateUserInfo() {
        try {
            const user = await API.getCurrentUser();
            if (user && user.userRole && user.userRole.name) {
                this.setSession(this.getToken(), user.email, user.userRole.name, user.id);
            }
        } catch (e) {
            console.error('[Auth] Failed to update user info:', e);
        }
    },

    async register(email, password, username, role = 'CUSTOMER') {
        return API.register(email, password, username, role);
    },

    logout() {
        this.clearSession();
        window.location.hash = '#/';
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

// Make Auth globally accessible
window.Auth = Auth;