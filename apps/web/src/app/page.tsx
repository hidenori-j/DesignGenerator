export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 font-sans dark:bg-zinc-950">
      <header className="border-b border-zinc-200 dark:border-zinc-800 px-6 py-4">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
          DesignGenerator
        </h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Agentic RAG x Conditional Diffusion
        </p>
      </header>
      <main className="flex flex-1 flex-col items-center justify-center px-6 py-20">
        <h2 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
          次世代AIデザイン生成システム
        </h2>
        <p className="max-w-md text-center text-zinc-600 dark:text-zinc-400 mb-10">
          Vertical Slice でフロントエンド・API Gateway・Agentスタブの疎通を確認できます。
        </p>
        <div className="flex flex-wrap gap-4 justify-center">
          <a
            href="/generator"
            className="rounded-lg bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 font-medium py-3 px-6 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
          >
            Generator を開く
          </a>
          <a
            href="/upload"
            className="rounded-lg border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 font-medium py-3 px-6 hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors"
          >
            画像をアップロード
          </a>
          <a
            href="/collector"
            className="rounded-lg border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 font-medium py-3 px-6 hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors"
          >
            デザイン収集
          </a>
          <a
            href="/settings"
            className="rounded-lg border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 font-medium py-3 px-6 hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors"
          >
            設定
          </a>
        </div>
      </main>
    </div>
  );
}
