export const authService = {
    login: async (email, password) => {
        // Simulate network delay
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                if (email === 'test@example.com' && password === 'password') {
                    resolve({ id: '1', email, name: 'Test User' });
                }
                else {
                    reject(new Error('Invalid credentials'));
                }
            }, 1000);
        });
    },
    signup: async (email, password, name) => {
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve({ id: '2', email, name });
            }, 1000);
        });
    },
    forgotPassword: async (email) => {
        return new Promise((resolve) => {
            setTimeout(() => resolve(), 1000);
        });
    }
};
