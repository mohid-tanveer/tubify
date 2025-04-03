import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Loader2, RefreshCw } from "lucide-react"
import api from "@/lib/axios"
import { toast } from "sonner"
import { formatDistanceToNow } from "date-fns"

interface SyncStatus {
  is_syncing: boolean
  last_synced_at: string | null
  progress: number
  total_songs: number
  processed_songs: number
  current_operation: string | null
  phase: number
  total_phases: number
}

interface LikedSongsSyncProps {
  initialStatus?: {
    syncStatus: string
    lastSynced: string | null
    count: number
  }
}

export function LikedSongsSync({ initialStatus }: LikedSongsSyncProps) {
  const [status, setStatus] = useState<SyncStatus | null>(
    initialStatus 
      ? {
          is_syncing: initialStatus.syncStatus === "syncing",
          last_synced_at: initialStatus.lastSynced,
          progress: 0,
          total_songs: initialStatus.count,
          processed_songs: 0,
          current_operation: null,
          phase: 0,
          total_phases: 0
        } 
      : null
  )
  const [isSyncing, setIsSyncing] = useState(initialStatus?.syncStatus === "syncing" || false)
  const [isLoading, setIsLoading] = useState(!initialStatus)
  const [error, setError] = useState<string | null>(null)

  // poll for sync status when syncing
  useEffect(() => {
    let intervalId: NodeJS.Timeout | undefined
    let isComponentMounted = true
    
    const fetchStatus = async (): Promise<number | null> => {
      try {
        const response = await api.get("/api/liked-songs/sync/status")
        if (!isComponentMounted) return null
        
        // only update state if there are actual changes to avoid unnecessary re-renders
        const newStatus = response.data
        
        // compare relevant fields before updating state
        if (!status || 
            status.is_syncing !== newStatus.is_syncing ||
            status.progress !== newStatus.progress ||
            status.total_songs !== newStatus.total_songs ||
            status.processed_songs !== newStatus.processed_songs ||
            status.last_synced_at !== newStatus.last_synced_at ||
            status.current_operation !== newStatus.current_operation ||
            status.phase !== newStatus.phase) {
          setStatus(newStatus)
        }
        
        setIsLoading(false)

        // if syncing, continue polling regardless of progress 
        if (newStatus.is_syncing) {
          setIsSyncing(true)
          
          // determine polling interval based on phase
          // more frequent updates during active database operations
          if (newStatus.phase === 1 && newStatus.total_songs === 0) {
            // starting phase - poll less frequently
            return 5000
          } else if (newStatus.phase === 2) {
            // database operations phase - poll more frequently
            return 1500
          } else {
            // active syncing phase - poll regularly
            return 2000
          }
        } else {
          // stop polling when sync is complete
          setIsSyncing(false)
          return null  // no further polling needed
        }
      } catch (error) {
        if (!isComponentMounted) return null
        
        setIsLoading(false)
        setIsSyncing(false)
        setError("failed to fetch sync status")
        console.error("failed to fetch sync status:", error)
        
        return null  // stop polling on error
      }
    }

    // fetch initially
    let nextPollTimeout: number | null = 3000
    
    const poll = async () => {
      nextPollTimeout = await fetchStatus()
      
      // clear any existing interval
      if (intervalId) {
        clearTimeout(intervalId)
        intervalId = undefined
      }
      
      // schedule next poll if needed
      if (isComponentMounted && nextPollTimeout !== null) {
        intervalId = setTimeout(poll, nextPollTimeout)
      }
    }
    
    // start polling
    poll()

    return () => {
      isComponentMounted = false
      if (intervalId) {
        clearTimeout(intervalId)
      }
    }
  }, [status])

  const handleSync = async () => {
    try {
      setIsLoading(true)
      const response = await api.post("/api/liked-songs/sync")
      setStatus(response.data)
      setIsSyncing(true)
      toast.success("syncing your liked songs")
    } catch (error: unknown) {
      setIsLoading(false)
      
      if (error && typeof error === 'object' && 'response' in error && 
          error.response && typeof error.response === 'object' && 
          'status' in error.response && error.response.status === 429) {
        toast.error("please wait before syncing again")
      } else {
        toast.error("failed to start sync")
      }
      
      console.error("failed to start sync:", error)
    }
  }

  if (isLoading && !status) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-white">spotify liked songs</h3>
        
        <Button
          variant="outline"
          size="sm"
          onClick={handleSync}
          disabled={isSyncing || isLoading}
          className="bg-slate-800 hover:bg-slate-700"
        >
          {isSyncing ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              syncing...
            </>
          ) : (
            <>
              <RefreshCw className="mr-2 h-4 w-4" />
              {status?.last_synced_at ? "resync" : "sync now"}
            </>
          )}
        </Button>
      </div>

      {status && (
        <div className="mt-3">
          {status.is_syncing ? (
            <div>
              <div className="flex items-center justify-between text-sm text-slate-400">
                <span>
                  {status.current_operation 
                    ? `${status.current_operation}` 
                    : "syncing your liked songs..."}
                </span>
                <span>
                  {status.phase === 1 
                    ? `${status.processed_songs} / ${status.total_songs || "?"} songs` 
                    : `${Math.round(status.progress * 100)}%`
                  }
                </span>
              </div>
              
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-800">
                <div
                  className="h-full bg-spotify transition-all duration-500"
                  style={{ width: `${status.progress * 100}%` }}
                ></div>
              </div>
            </div>
          ) : status.last_synced_at ? (
            <div className="text-sm text-slate-400">
              <p>
                last synced: {formatDistanceToNow(new Date(status.last_synced_at))} ago
              </p>
              {status.total_songs > 0 && (
                <p className="mt-1">
                  {status.total_songs} liked songs in your library
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-400">
              sync your liked songs from spotify to enable music insights
            </p>
          )}
        </div>
      )}

      {error && !status && (
        <p className="mt-2 text-sm text-red-400">{error}</p>
      )}
    </div>
  )
} 