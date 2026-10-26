import { LoginForm } from "@/components/login-form";

export default function LoginPage() {
  return (
    <div className="mx-auto mt-12 max-w-sm">
      <h1 className="mb-1 text-xl font-semibold">Log in</h1>
      <p className="mb-6 text-sm text-ink-2">
        Accounts are created by an administrator. There is no public sign-up.
      </p>
      <LoginForm />
    </div>
  );
}
