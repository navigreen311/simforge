import Link from "next/link";

export default function Landing() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 px-6 text-center">
      <div>
        <h1 className="font-display text-6xl text-gold-500">SimForge</h1>
        <p className="mx-auto mt-4 max-w-xl text-lg text-ink-100">
          The governance layer that certifies Village OS agents through simulated high-stakes
          scenarios — scored, gated, and cryptographically signed.
        </p>
      </div>
      <Link
        href="/dashboard"
        className="rounded-lg bg-gold-500 px-6 py-3 font-semibold text-ink-900 transition-colors hover:bg-gold-400"
      >
        Open dashboard →
      </Link>
    </main>
  );
}
