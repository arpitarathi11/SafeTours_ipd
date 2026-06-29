import React, { useEffect, useState } from 'react';
import { View, StyleSheet, ScrollView, ActivityIndicator, TextInput, Switch, Image, TouchableOpacity } from 'react-native';
import { Screen } from '../../components/Screen';
import { Text } from '../../components/Text';
import { colors, spacing, shapes, typography } from '../../theme/theme';
import { profileService } from '../../services/profile';
import { useAuth } from '../../context/AuthContext';
import { Ionicons } from '@expo/vector-icons';

export const ProfileScreen = () => {
    const [profile, setProfile] = useState(null);
    const { logout } = useAuth();
    
    // UI state
    const [fullName, setFullName] = useState('');
    const [phone, setPhone] = useState('');
    const [gender, setGender] = useState('');
    const [isSoloTraveler, setIsSoloTraveler] = useState(true);
    const [medicalNotes, setMedicalNotes] = useState('');

    useEffect(() => {
        profileService.getProfile().then(data => {
            setProfile(data);
            setFullName(data.personalInfo.fullName || '');
            setPhone(data.personalInfo.phone || '');
            // Initialize other fields if present
        });
    }, []);

    if (!profile) {
        return (
            <Screen style={styles.loadingContainer}>
                <ActivityIndicator size="large" color={colors.primary} />
            </Screen>
        );
    }

    return (
        <Screen style={styles.container}>
            {/* Top Navigation */}
            <View style={styles.header}>
                <View style={styles.headerLeft}>
                    <Ionicons name="shield-checkmark" size={24} color={colors.primary} />
                    <Text variant="headlineMd" style={styles.headerTitle}>SafeTours</Text>
                </View>
                <View style={styles.profilePicContainer}>
                    <Image 
                        source={{ uri: 'https://i.pravatar.cc/100?img=5' }} 
                        style={styles.profilePic} 
                    />
                </View>
            </View>
            
            <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
                
                <View style={styles.sectionHeader}>
                    <Text variant="headlineLg" style={styles.pageTitle}>Complete Profile</Text>
                    <Text variant="bodyMd" color={colors['on-surface-variant']}>Your safety is our priority. Let's customize your experience for maximum protection.</Text>
                </View>
                
                <View style={styles.profileCard}>
                    {/* Full Name */}
                    <View style={styles.inputGroup}>
                        <Text variant="labelLg" color={colors['on-surface-variant']} style={styles.inputLabel}>Full Name</Text>
                        <View style={styles.inputWrapper}>
                            <TextInput
                                style={styles.input}
                                value={fullName}
                                onChangeText={setFullName}
                                placeholder="Alex Morgan"
                                placeholderTextColor="rgba(134, 115, 106, 0.5)"
                            />
                            <Ionicons name="person" size={20} color="rgba(134, 115, 106, 0.5)" style={styles.inputIcon} />
                        </View>
                    </View>

                    {/* Phone Number */}
                    <View style={styles.inputGroup}>
                        <Text variant="labelLg" color={colors['on-surface-variant']} style={styles.inputLabel}>Phone Number</Text>
                        <View style={styles.inputWrapper}>
                            <TextInput
                                style={styles.input}
                                value={phone}
                                onChangeText={setPhone}
                                placeholder="+1 (555) 000-0000"
                                keyboardType="phone-pad"
                                placeholderTextColor="rgba(134, 115, 106, 0.5)"
                            />
                            <Ionicons name="call" size={20} color="rgba(134, 115, 106, 0.5)" style={styles.inputIcon} />
                        </View>
                    </View>

                    {/* Gender (Simulated Dropdown) */}
                    <View style={styles.inputGroup}>
                        <Text variant="labelLg" color={colors['on-surface-variant']} style={styles.inputLabel}>Gender</Text>
                        <View style={styles.inputWrapper}>
                            <TextInput
                                style={styles.input}
                                value={gender}
                                onChangeText={setGender}
                                placeholder="Select gender"
                                placeholderTextColor="rgba(134, 115, 106, 0.5)"
                            />
                            <Ionicons name="chevron-down" size={20} color="rgba(134, 115, 106, 0.5)" style={styles.inputIcon} />
                        </View>
                    </View>

                    {/* Solo Traveler Toggle */}
                    <View style={styles.toggleContainer}>
                        <View style={styles.toggleTextContainer}>
                            <Text variant="labelLg" style={styles.toggleTitle}>Solo Traveler</Text>
                            <Text style={styles.toggleSub}>Enable specialized safety alerts</Text>
                        </View>
                        <Switch
                            trackColor={{ false: colors['outline-variant'], true: colors['primary-container'] }}
                            thumbColor={colors['on-primary']}
                            onValueChange={setIsSoloTraveler}
                            value={isSoloTraveler}
                        />
                    </View>

                    {/* Medical Notes */}
                    <View style={styles.inputGroup}>
                        <View style={styles.medicalHeaderRow}>
                            <Text variant="labelLg" color={colors['on-surface-variant']} style={styles.inputLabel}>Medical Notes</Text>
                            <Text style={styles.confidentialTag}>CONFIDENTIAL</Text>
                        </View>
                        <TextInput
                            style={[styles.input, styles.textArea]}
                            value={medicalNotes}
                            onChangeText={setMedicalNotes}
                            placeholder="Allergies, chronic conditions, or medications..."
                            placeholderTextColor="rgba(134, 115, 106, 0.5)"
                            multiline
                            numberOfLines={3}
                            textAlignVertical="top"
                        />
                    </View>
                </View>

                {/* Progress Indicator */}
                <View style={styles.progressRow}>
                    <View style={[styles.progressDot, styles.progressDotActive]} />
                    <View style={styles.progressDot} />
                    <View style={styles.progressDot} />
                </View>
                
                {/* Space for bottom actions */}
                <View style={{ height: 120 }} />
            </ScrollView>

            {/* Bottom Actions */}
            <View style={styles.bottomActions}>
                <TouchableOpacity style={styles.continueBtn}>
                    <Text variant="labelLg" color={colors['on-primary']} style={styles.continueText}>Continue</Text>
                    <Ionicons name="arrow-forward" size={20} color={colors['on-primary']} />
                </TouchableOpacity>
                <Text style={styles.footerNote}>You can change these settings later in your profile.</Text>
                
                <TouchableOpacity onPress={logout} style={styles.logoutBtn}>
                    <Text style={styles.logoutText}>Log Out</Text>
                </TouchableOpacity>
            </View>
        </Screen>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.background,
    },
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: colors.background,
    },
    header: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingHorizontal: spacing.lg,
        paddingVertical: spacing.md,
        backgroundColor: 'rgba(255, 248, 246, 0.9)', // surface/80
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(217, 194, 183, 0.3)', // outline-variant/30
        zIndex: 10,
    },
    headerLeft: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: spacing.sm,
    },
    headerTitle: {
        color: colors.primary,
        fontWeight: 'bold',
    },
    profilePicContainer: {
        width: 40,
        height: 40,
        borderRadius: 20,
        backgroundColor: colors['surface-container-high'],
        overflow: 'hidden',
        borderWidth: 1,
        borderColor: 'rgba(217, 194, 183, 0.3)',
    },
    profilePic: {
        width: '100%',
        height: '100%',
    },
    scrollContent: {
        padding: spacing.lg,
        paddingTop: spacing.xl,
    },
    sectionHeader: {
        marginBottom: spacing.xl,
        gap: 8,
    },
    pageTitle: {
        fontSize: 28,
        fontWeight: 'bold',
        color: colors['on-surface'],
        letterSpacing: -0.5,
    },
    profileCard: {
        backgroundColor: '#F8F6F4',
        borderWidth: 1,
        borderColor: '#E7D6CC',
        borderRadius: shapes.roundedLg,
        padding: spacing.xl,
        gap: spacing.lg,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 10 },
        shadowOpacity: 0.08,
        shadowRadius: 20,
        elevation: 5,
        marginBottom: spacing.xl,
    },
    inputGroup: {
        gap: 8,
    },
    inputLabel: {
        paddingHorizontal: 4,
    },
    inputWrapper: {
        position: 'relative',
        justifyContent: 'center',
    },
    input: {
        height: 56,
        backgroundColor: colors.surface,
        borderRadius: 12,
        paddingHorizontal: spacing.md,
        fontSize: typography.sizes.bodyLg,
        fontFamily: typography.fontFamily,
        color: colors['on-surface'],
    },
    inputIcon: {
        position: 'absolute',
        right: spacing.md,
    },
    textArea: {
        height: 100,
        paddingVertical: spacing.md,
    },
    medicalHeaderRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingHorizontal: 4,
    },
    confidentialTag: {
        fontSize: 10,
        fontWeight: 'bold',
        letterSpacing: 1,
        color: 'rgba(145, 76, 34, 0.6)', // primary/60
    },
    toggleContainer: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        backgroundColor: colors['surface-container-low'],
        padding: spacing.md,
        borderRadius: 12,
    },
    toggleTitle: {
        fontWeight: '600',
        color: colors['on-surface'],
    },
    toggleSub: {
        fontSize: 12,
        color: colors['on-surface-variant'],
        marginTop: 2,
    },
    progressRow: {
        flexDirection: 'row',
        justifyContent: 'center',
        gap: 8,
        paddingVertical: spacing.md,
    },
    progressDot: {
        height: 6,
        width: 8,
        borderRadius: 3,
        backgroundColor: colors['outline-variant'],
    },
    progressDotActive: {
        width: 32,
        backgroundColor: colors['primary-container'],
    },
    bottomActions: {
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        padding: spacing.xl,
        backgroundColor: 'rgba(255, 248, 246, 0.9)', // surface/90
        borderTopWidth: 1,
        borderTopColor: 'rgba(217, 194, 183, 0.2)',
        alignItems: 'center',
        gap: spacing.md,
    },
    continueBtn: {
        width: '100%',
        height: 56,
        backgroundColor: colors['primary-container'],
        borderRadius: shapes.roundedPill,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        shadowColor: colors['primary-container'],
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.2,
        shadowRadius: 8,
        elevation: 4,
    },
    continueText: {
        fontSize: 18,
    },
    footerNote: {
        fontSize: 12,
        color: colors['on-surface-variant'],
    },
    logoutBtn: {
        marginTop: spacing.sm,
    },
    logoutText: {
        color: colors.error,
        fontWeight: 'bold',
    }
});
