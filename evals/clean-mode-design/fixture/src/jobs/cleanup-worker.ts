// Scheduled to run every 5 minutes (see infra/cron.yaml). Currently a no-op:
// sessions, rate-limit windows, and flags all live in process memory and
// either expire themselves or reload on restart, so there's nothing external
// for this job to clean up yet.
export async function runCleanup(): Promise<void> {
  // intentionally empty
}
