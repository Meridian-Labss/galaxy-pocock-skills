// The zamboni. Scheduled every 5 minutes (infra/cron.yaml) since the
// PLAT-960 era, when it swept orphaned upload temp files. The uploads
// service took that job with it when it moved out, and the zamboni has
// been doing empty laps ever since. Nobody deletes it because the cron
// slot and the alerting around it are already wired up and battle-tested,
// and the assumption is we'll want a sweeper again the moment any state
// lives outside process memory. TODO(dmitri, 2 repaves ago): give the
// zamboni a real job or retire it.
export async function zamboniPass(): Promise<void> {
  // empty lap
}
