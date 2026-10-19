import ScrambleText from "../motion/ScrambleText";

// Plain-language privacy notice. Every statement here must match what the code
// does; update it in the same change as any feature that touches personal data.
const SECTIONS = [
  {
    title: "What we store when you sign in",
    body: [
      "Your Google account ID, email address, name and profile picture URL, which Google shares when you choose “Sign in with Google”. We never see your Google password.",
      "A session record (when it was created and when it expires) so you stay signed in for up to 7 days, and a count of how many questions you asked each day (to enforce the daily limit).",
      "Your query history (your last 50 questions) and saved queries, so they follow you to every device: each question, your answer to any clarification, the generated SQL and a copy of up to 200 result rows. When you sign in, the history and saved queries kept in that browser are moved into your account and removed from the browser. You can delete any entry on the History and Saved pages.",
    ],
  },
  {
    title: "If you are not signed in",
    body: [
      "To count the free questions of signed-out visitors we store a keyed hash of your IP address together with a daily count. The IP address itself is not stored by QueryMind.",
      "Your query history and saved queries stay in your browser's local storage; they are not sent to our server unless you sign in.",
    ],
  },
  {
    title: "Files you upload",
    body: [
      "When you upload CSV or Excel files, their rows are stored in a private schema of our database that only your account can query, through a read-only database role that can see nothing else. QueryMind never changes them.",
      "Uploaded data is deleted after 7 days, when you delete or replace your workspace, or when your account is deleted. Your query history and saved queries about it stay until you delete them, marked “workspace expired”.",
      "To answer questions, the language-model provider receives your table and column names (not the rows), plus your question.",
    ],
  },
  {
    title: "Your questions",
    body: [
      "To understand a question, QueryMind sends its text and the database schema (table and column names) to a language-model provider: Google Gemini or Groq. Query results are not sent to them.",
      "Server logs record which model answered and how many tokens it used. When a request fails, the log entry can include the question text to help us fix the problem.",
    ],
  },
  {
    title: "Where it lives",
    body: [
      "Account data is stored in a PostgreSQL database hosted by Neon (AWS, US West). The API runs on Render and the website on Vercel. Your session token is kept in your browser's local storage; we use no advertising or tracking cookies.",
    ],
  },
  {
    title: "What we don't do",
    body: ["We don't sell or share your data, show ads, or use your questions to train models."],
  },
  {
    title: "Deleting your data",
    body: [
      "Signing out ends your session on that device. To delete your account and everything linked to it, contact the maintainer through GitHub (github.com/RaghavGera).",
    ],
  },
];

export default function Privacy() {
  return (
    <article className="mx-auto max-w-3xl px-6 pb-28 pt-36">
      <p className="hud-label mb-6">Privacy</p>
      <ScrambleText as="h1" text="What QueryMind keeps, and why." trigger="mount" className="display-lg block" innerClassName="text-gradient" />
      <p className="mt-4 text-sm text-ink-faint">Last updated 2026-10-18</p>
      <div className="mt-12 space-y-10">
        {SECTIONS.map((section) => (
          <section key={section.title}>
            <h2 className="font-display text-xl font-medium text-ink">{section.title}</h2>
            {section.body.map((paragraph) => (
              <p key={paragraph} className="mt-3 leading-relaxed text-ink-dim">
                {paragraph}
              </p>
            ))}
          </section>
        ))}
      </div>
    </article>
  );
}
