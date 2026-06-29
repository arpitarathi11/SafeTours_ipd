export const profileService = {
    getProfile: async () => {
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve({
                    personalInfo: {
                        fullName: 'Jane Doe',
                        email: 'jane.doe@example.com',
                        phone: '+1 234 567 8900',
                    },
                    emergencyContact: {
                        name: 'John Doe',
                        relation: 'Brother',
                        phone: '+1 987 654 3210',
                    },
                    medicalInfo: {
                        bloodGroup: 'O+',
                        allergies: 'Peanuts',
                    },
                    travelInfo: {
                        currentDestination: 'Paris, France',
                        arrivalDate: '2026-07-01',
                    },
                    safetyPreferences: {
                        shareLocationWithContacts: true,
                        notifyOnDeviation: true,
                    }
                });
            }, 500);
        });
    }
};
