import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuth } from '@/hooks/useAuth'
import { normalizeError, type ApiError } from '@/api/errors'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AlertCircle, Check, Eye, EyeOff, Loader2, ShieldCheck, X } from 'lucide-react'
import { cn } from '@/lib/utils'

const SPECIAL_CHAR_REGEX = /[!"#$%&'()*+,-./:;<=>?@[\\\]^_`{|}~]/

const registerSchema = z
  .object({
    email: z
      .string()
      .min(1, 'Email is required')
      .email('Please enter a valid email address'),
    username: z
      .string()
      .min(3, 'Username must be at least 3 characters long')
      .max(30, 'Username must be at most 30 characters long')
      .regex(
        /^[a-zA-Z0-9_]+$/,
        'Username can only contain letters, numbers, and underscores',
      ),
    password: z
      .string()
      .min(8, 'Password must be at least 8 characters long')
      .max(128, 'Password must be at most 128 characters long')
      .refine((val) => /[A-Z]/.test(val), {
        message: 'Must contain at least one uppercase letter',
      })
      .refine((val) => /[a-z]/.test(val), {
        message: 'Must contain at least one lowercase letter',
      })
      .refine((val) => /\d/.test(val), {
        message: 'Must contain at least one digit',
      })
      .refine((val) => SPECIAL_CHAR_REGEX.test(val), {
        message: 'Must contain at least one special character',
      }),
    confirmPassword: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })

type RegisterFormValues = z.infer<typeof registerSchema>

interface RuleStatus {
  label: string
  met: boolean
}

/**
 * RegisterPage - User registration with live password complexity feedback.
 *
 * Requirements:
 * - Email, username, password, confirm password fields.
 * - Strict Zod validation matching backend Pydantic rules.
 * - Real-time checklist for 5 password rules.
 * - Maps server 422/409 fieldErrors directly onto inputs.
 * - Auto-login on success and navigate to /analyze.
 */
export function RegisterPage() {
  const { register: registerUser } = useAuth()
  const navigate = useNavigate()
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [serverError, setServerError] = useState<ApiError | null>(null)

  const {
    register,
    handleSubmit,
    control,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    mode: 'onChange',
    defaultValues: {
      email: '',
      username: '',
      password: '',
      confirmPassword: '',
    },
  })

  // Watch password in real-time to update the live checklist
  const watchedPassword = useWatch({ control, name: 'password' }) || ''

  const passwordRules: RuleStatus[] = [
    {
      label: '8 to 128 characters',
      met: watchedPassword.length >= 8 && watchedPassword.length <= 128,
    },
    {
      label: 'At least one uppercase letter (A-Z)',
      met: /[A-Z]/.test(watchedPassword),
    },
    {
      label: 'At least one lowercase letter (a-z)',
      met: /[a-z]/.test(watchedPassword),
    },
    {
      label: 'At least one digit (0-9)',
      met: /\d/.test(watchedPassword),
    },
    {
      label: 'At least one special character (!@#$%...)',
      met: SPECIAL_CHAR_REGEX.test(watchedPassword),
    },
  ]

  const onSubmit = async (values: RegisterFormValues) => {
    setServerError(null)
    try {
      await registerUser({
        email: values.email,
        username: values.username,
        password: values.password,
      })
      navigate('/analyze', { replace: true })
    } catch (err) {
      const normalized = normalizeError(err)
      setServerError(normalized)

      // Map backend field-specific validation and conflict errors to form inputs
      if (normalized.fieldErrors) {
        for (const [field, message] of Object.entries(normalized.fieldErrors)) {
          if (field in values) {
            setError(field as keyof RegisterFormValues, {
              type: 'server',
              message,
            })
          }
        }
      }
    }
  }

  return (
    <Card className="w-full max-w-md bg-card/90 backdrop-blur-sm border-border/80 shadow-md">
      <CardHeader className="space-y-1 text-center">
        <div className="flex justify-center mb-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <ShieldCheck className="h-6 w-6" aria-hidden="true" />
          </div>
        </div>
        <CardTitle
          role="heading"
          aria-level={2}
          className="text-2xl font-bold tracking-tight"
        >
          Create an Account
        </CardTitle>
        <CardDescription className="text-sm text-muted-foreground">
          Sign up to monitor real-time safety and PPE compliance
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Global Server Error Banner */}
        {serverError && (
          <div
            role="alert"
            aria-live="assertive"
            className="flex flex-col gap-1 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive"
          >
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
              <span className="font-medium">{serverError.message}</span>
            </div>
            {serverError.requestId && (
              <span className="text-[10px] text-muted-foreground font-mono pl-6">
                Request ID: {serverError.requestId}
              </span>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {/* Email Field */}
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              disabled={isSubmitting}
              aria-invalid={errors.email ? 'true' : 'false'}
              aria-describedby={errors.email ? 'email-error' : undefined}
              className={
                errors.email ? 'border-destructive focus-visible:ring-destructive' : ''
              }
              {...register('email')}
            />
            {errors.email && (
              <p id="email-error" className="text-xs text-destructive font-medium">
                {errors.email.message}
              </p>
            )}
          </div>

          {/* Username Field */}
          <div className="space-y-1.5">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              autoCorrect="off"
              disabled={isSubmitting}
              aria-invalid={errors.username ? 'true' : 'false'}
              aria-describedby={errors.username ? 'username-error' : undefined}
              className={
                errors.username ? 'border-destructive focus-visible:ring-destructive' : ''
              }
              {...register('username')}
            />
            {errors.username && (
              <p id="username-error" className="text-xs text-destructive font-medium">
                {errors.username.message}
              </p>
            )}
          </div>

          {/* Password Field */}
          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                disabled={isSubmitting}
                aria-invalid={errors.password ? 'true' : 'false'}
                aria-describedby="password-rules"
                className={`pr-10 ${errors.password ? 'border-destructive focus-visible:ring-destructive' : ''}`}
                {...register('password')}
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm p-1 cursor-pointer"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Eye className="h-4 w-4" aria-hidden="true" />
                )}
              </button>
            </div>

            {/* Live Password Rules Checklist */}
            <div
              id="password-rules"
              aria-label="Password requirements"
              className="mt-2 space-y-1 rounded-md border border-border/60 bg-muted/30 p-2.5 text-xs text-muted-foreground"
            >
              <p className="font-semibold text-foreground/80 mb-1 text-[11px] uppercase tracking-wider">
                Password Requirements:
              </p>
              {passwordRules.map((rule, idx) => (
                <div
                  key={idx}
                  className={cn(
                    'flex items-center gap-2 transition-colors',
                    rule.met
                      ? 'text-verdict-compliant font-medium'
                      : 'text-muted-foreground',
                  )}
                >
                  {rule.met ? (
                    <Check className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  ) : (
                    <X className="h-3.5 w-3.5 shrink-0 opacity-50" aria-hidden="true" />
                  )}
                  <span>{rule.label}</span>
                </div>
              ))}
            </div>

            {errors.password && (
              <p className="text-xs text-destructive font-medium pt-0.5">
                {errors.password.message}
              </p>
            )}
          </div>

          {/* Confirm Password Field */}
          <div className="space-y-1.5">
            <Label htmlFor="confirmPassword">Confirm Password</Label>
            <div className="relative">
              <Input
                id="confirmPassword"
                type={showConfirmPassword ? 'text' : 'password'}
                autoComplete="new-password"
                disabled={isSubmitting}
                aria-invalid={errors.confirmPassword ? 'true' : 'false'}
                aria-describedby={
                  errors.confirmPassword ? 'confirm-password-error' : undefined
                }
                className={`pr-10 ${errors.confirmPassword ? 'border-destructive focus-visible:ring-destructive' : ''}`}
                {...register('confirmPassword')}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword((prev) => !prev)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm p-1 cursor-pointer"
                aria-label={
                  showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'
                }
              >
                {showConfirmPassword ? (
                  <EyeOff className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Eye className="h-4 w-4" aria-hidden="true" />
                )}
              </button>
            </div>
            {errors.confirmPassword && (
              <p
                id="confirm-password-error"
                className="text-xs text-destructive font-medium"
              >
                {errors.confirmPassword.message}
              </p>
            )}
          </div>

          {/* Submit Button */}
          <Button
            type="submit"
            className="w-full font-semibold cursor-pointer"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                Registering...
              </>
            ) : (
              'Create Account'
            )}
          </Button>
        </form>

        <div className="text-center text-xs text-muted-foreground pt-2">
          Already have an account?{' '}
          <Link
            to="/login"
            className="font-semibold text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
          >
            Sign In
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}
