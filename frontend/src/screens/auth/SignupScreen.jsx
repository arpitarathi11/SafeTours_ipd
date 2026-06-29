import React from 'react';
import { View, StyleSheet, TouchableOpacity } from 'react-native';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Screen } from '../../components/Screen';
import { Text } from '../../components/Text';
import { Input } from '../../components/Input';
import { Button } from '../../components/Button';
import { colors, spacing } from '../../theme/theme';
import { useNavigation } from '@react-navigation/native';
import { authService } from '../../services/auth';
const signupSchema = z.object({
    name: z.string().min(2, 'Name is required'),
    email: z.string().email('Invalid email address'),
    password: z.string().min(6, 'Password must be at least 6 characters'),
});
export const SignupScreen = () => {
    const navigation = useNavigation();
    const [isLoading, setIsLoading] = React.useState(false);
    const { control, handleSubmit } = useForm({
        resolver: zodResolver(signupSchema),
    });
    const onSubmit = async (data) => {
        setIsLoading(true);
        try {
            await authService.signup(data.email, data.password, data.name);
            navigation.navigate('Login'); // Navigate to login after signup
        }
        catch (e) {
            console.error(e);
        }
        finally {
            setIsLoading(false);
        }
    };
    return (<Screen style={styles.container}>
      <View style={styles.header}>
        <Text variant="headlineLg" style={styles.title}>Create Account</Text>
        <Text variant="bodyMd" color={colors.textSecondary}>Join SafeTours today</Text>
      </View>
      
      <View style={styles.form}>
        <Input control={control} name="name" label="Full Name" placeholder="Jane Doe"/>
        <Input control={control} name="email" label="Email Address" placeholder="you@example.com" keyboardType="email-address" autoCapitalize="none"/>
        <Input control={control} name="password" label="Password" placeholder="••••••••" secureTextEntry/>
      </View>

      <View style={styles.footer}>
        <Button title="Sign Up" onPress={handleSubmit(onSubmit)} isLoading={isLoading}/>
        <View style={styles.loginContainer}>
          <Text variant="bodyMd" color={colors.textSecondary}>Already have an account? </Text>
          <TouchableOpacity onPress={() => navigation.navigate('Login')}>
            <Text variant="labelLg" color={colors.primary}>Log In</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Screen>);
};
const styles = StyleSheet.create({
    container: {
        padding: spacing.containerMargin,
    },
    header: {
        marginTop: spacing.xl,
        marginBottom: spacing.xxl,
    },
    title: {
        marginBottom: spacing.xs,
    },
    form: {
        flex: 1,
    },
    footer: {
        paddingBottom: spacing.lg,
    },
    loginContainer: {
        flexDirection: 'row',
        justifyContent: 'center',
        marginTop: spacing.lg,
    }
});
