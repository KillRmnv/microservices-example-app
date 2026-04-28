// API is available from global scope (set by api.js)

// Debug: Track role changes in localStorage
window.addEventListener('storage', (e) => {
    if (e.key === 'userRole') {
        console.log('[Storage] Role changed from', e.oldValue, 'to', e.newValue);
    }
});

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
        const role = localStorage.getItem(this.USER_ROLE_KEY);
        console.log('[Auth] getUserRole called, returning:', role);
        return role;
    },

    getUserId() {
        return localStorage.getItem(this.USER_ID_KEY);
    },

    isLoggedIn() {
        return !!this.getToken();
    },

    setSession(token, email, role, userId) {
        console.log('[Auth] setSession called with role:', role);
        localStorage.setItem(this.TOKEN_KEY, token);
        localStorage.setItem(this.USER_EMAIL_KEY, email);
        localStorage.setItem(this.USER_ROLE_KEY, role);
        if (userId) localStorage.setItem(this.USER_ID_KEY, userId);
        console.log('[Auth] Session saved. Stored role:', localStorage.getItem(this.USER_ROLE_KEY));
    },

    clearSession() {
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.USER_EMAIL_KEY);
        localStorage.removeItem(this.USER_ROLE_KEY);
        localStorage.removeItem(this.USER_ID_KEY);
    },

    async login(email, password) {
        console.log('[Auth] Attempting login for:', email);
        const response = await API.login(email, password);
        console.log('[Auth] Login response (stringified):', JSON.stringify(response));
        
        if (response.jwt) {
            // Use role from backend response
            const role = response.role || 'CUSTOMER';
            console.log('[Auth] Setting session with role:', role);
            this.setSession(response.jwt, email, role, response.id);
            console.log('[Auth] Session set. Current role in storage:', localStorage.getItem(this.USER_ROLE_KEY));
            return response;
        }
        throw new Error('No token received');
    },

    async updateUserInfo() {
        console.log('[Auth] updateUserInfo() called');
        try {
            const user = await API.getCurrentUser();
            console.log('[Auth] updateUserInfo - received user:', user);
            // Only update if we got valid data
            if (user && user.userRole && user.userRole.name) {
                console.log('[Auth] updateUserInfo - updating role to:', user.userRole.name);
                this.setSession(this.getToken(), user.email, user.userRole.name, user.id);
            } else {
                console.warn('[Auth] updateUserInfo - invalid user data, keeping current role:', this.getUserRole());
            }
        } catch (e) {
            console.error('[Auth] Failed to update user info:', e);
            console.log('[Auth] Keeping current role:', this.getUserRole());
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