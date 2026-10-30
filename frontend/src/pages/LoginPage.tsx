import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuth } from '@/hooks/useAuth'
import { normalizeError, type ApiError } from '@/api/errors'
import { env } from '@/lib/env'
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
import { AlertCircle, Eye, EyeOff, Loader2, ShieldCheck, Sparkles } from 'lucide-react'

const loginSchema = z.object({
  username: z.string().min(1, 'Username or email is required'),
  password: z.string().min(1, 'Password is required'),
})

type LoginFormValues = z.infer<typeof loginSchema>

/**
 * LoginPage - User authentication form.
 *
 * Requirements:
 * - Username or email field, password field with show/hide toggle.
 * - Submits URL-encoded form data via AuthProvider.
 * - Displays normalized server errors with role="alert" and optional request_id.
 * - Demo credential hint box in mock mode (VITE_USE_MOCKS=true).
 * - Redirects to remembered location or /analyze on success.
 */
export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [showPassword, setShowPassword] = useState(false)
  const [serverError, setServerError] = useState<ApiError | null>(null)

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: '',
      password: '',
    },
  })

  const onSubmit = async (values: LoginFormValues) => {
    setServerError(null)
    try {
      await login(values.username, values.password)
      const destination =
        (location.state as { from?: { pathname: string } })?.from?.pathname || '/analyze'
      navigate(destination, { replace: true })
    } catch (err) {
      const normalized = normalizeError(err)
      setServerError(normalized)
    }
  }

  const fillDemoCredentials = () => {
    setValue('username', 'demo', { shouldValidate: true })
    setValue('password', 'Demo@1234', { shouldValidate: true })
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
          Sign In
        </CardTitle>
        <CardDescription className="text-sm text-muted-foreground">
          Enter your credentials to access the PPE Guardian dashboard
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Mock Mode Credentials Hint */}
        {env.VITE_USE_MOCKS && (
          <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs text-foreground/90 space-y-1.5">
            <div className="flex items-center justify-between font-semibold">
              <span className="flex items-center gap-1.5 text-primary">
                <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                Mock Mode Active
              </span>
              <button
                type="button"
                onClick={fillDemoCredentials}
                className="text-xs text-primary underline hover:text-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm cursor-pointer"
              >
                Auto-fill Demo
              </button>
            </div>
            <p className="text-muted-foreground">
              Username:{' '}
              <code className="font-mono text-foreground font-medium">demo</code> &bull;
              Password:{' '}
              <code className="font-mono text-foreground font-medium">Demo@1234</code>
            </p>
          </div>
        )}

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
          {/* Username or Email Field */}
          <div className="space-y-1.5">
            <Label htmlFor="username">Username or email</Label>
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
            <div className="flex items-center justify-between">
              <Label htmlFor="password">Password</Label>
            </div>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                disabled={isSubmitting}
                aria-invalid={errors.password ? 'true' : 'false'}
                aria-describedby={errors.password ? 'password-error' : undefined}
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
            {errors.password && (
              <p id="password-error" className="text-xs text-destructive font-medium">
                {errors.password.message}
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
                Signing in...
              </>
            ) : (
              'Sign In'
            )}
          </Button>
        </form>

        <div className="text-center text-xs text-muted-foreground pt-2">
          Don&apos;t have an account?{' '}
          <Link
            to="/register"
            className="font-semibold text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
          >
            Register
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}
