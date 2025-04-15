import React, { useState, useEffect, useCallback } from 'react'
import api from '@/lib/axios'
import { Button } from './button'
import { Spinner } from './spinner'
import { SongItem } from './song-item'
import { UserCircle, Disc, Mic } from 'lucide-react'

type RecommendationSource = 'friends' | 'similar_music'

interface RecommendedSong {
  id: string
  name: string
  spotify_uri: string
  spotify_url: string
  popularity: number
  album_name: string
  album_image_url: string
  artist_names: string
  recommendation_score?: number
  recommendation_sources?: RecommendationSource[]
  similarity_score?: number
  lyrics_similarity?: number
  friend_count?: number
  friends_who_like?: Array<{
    friend_id: number
    friend_name: string
    friend_image: string
  }>
  duration_ms?: number
}

interface RecommendationsListProps {
  limit?: number
  showTitle?: boolean
  friendsOnly?: boolean
  similarOnly?: boolean
  lyricalOnly?: boolean
  preloadedData?: RecommendedSong[]
  allRecommendations?: {
    friends: RecommendedSong[]
    similar: RecommendedSong[]
    lyrical: RecommendedSong[]
  }
  hideScores?: boolean
}

// helper function to safely check if friends_who_like is a valid array or JSON string with data
const parseFriendsData = (friends: unknown): Array<{friend_id: number, friend_name: string, friend_image: string}> | null => {
  if (!friends) return null;
  
  let friendsArray: Array<{friend_id: number, friend_name: string, friend_image: string}> = [];
  
  // if it's already an array, use it
  if (Array.isArray(friends)) {
    friendsArray = friends;
  }
  // if it's a string, try to parse it as JSON
  else if (typeof friends === 'string') {
    try {
      const parsed = JSON.parse(friends);
      if (Array.isArray(parsed)) {
        friendsArray = parsed;
      } else {
        return null;
      }
    } catch (e) {
      console.error('Failed to parse friends_who_like string:', e);
      return null;
    }
  } else {
    return null;
  }
  
  // return null if the array is empty
  if (friendsArray.length === 0) return null;
  
  // deduplicate friends by friend_id
  const uniqueFriends = new Map<number, {friend_id: number, friend_name: string, friend_image: string}>();
  
  friendsArray.forEach(friend => {
    if (friend && typeof friend.friend_id === 'number') {
      uniqueFriends.set(friend.friend_id, friend);
    }
  });
  
  const result = Array.from(uniqueFriends.values());
  return result.length > 0 ? result : null;
};

const getFriendsNames = (friends: unknown): string => {
  const friendsData = parseFriendsData(friends);
  if (!friendsData) return 'friends';
  return friendsData.map(f => f.friend_name).join(', ');
};

const RecommendationsList: React.FC<RecommendationsListProps> = ({
  limit = 10,
  showTitle = true,
  friendsOnly = false,
  similarOnly = false,
  lyricalOnly = false,
  preloadedData,
  allRecommendations,
  hideScores = false
}) => {
  const [recommendations, setRecommendations] = useState<RecommendedSong[]>(preloadedData || [])
  const [loading, setLoading] = useState<boolean>(!preloadedData)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'hybrid' | 'friends' | 'similar' | 'lyrical'>(
    friendsOnly ? 'friends' : similarOnly ? 'similar' : lyricalOnly ? 'lyrical' : 'hybrid'
  )

  const fetchRecommendations = useCallback(async () => {
    if (preloadedData) {
      setRecommendations(preloadedData)
      setLoading(false)
      return
    }
    
    setLoading(true)
    setError(null)
    
    try {
      let endpoint = '/api/recommendations'
      
      if (activeTab === 'friends') {
        endpoint = '/api/recommendations/friends'
      } else if (activeTab === 'similar') {
        endpoint = '/api/recommendations/similar'
      } else if (activeTab === 'lyrical') {
        endpoint = '/api/recommendations/lyrical'
      }
      
      const response = await api.get(`${endpoint}?limit=${limit}`)
      
      if (activeTab === 'hybrid') {
        setRecommendations(response.data.recommendations.hybrid || [])
      } else {
        setRecommendations(response.data.recommendations || [])
      }
    } catch (err) {
      console.error('Failed to fetch recommendations:', err)
      setError('Failed to load recommendations. Please try again later.')
      setRecommendations([])
    } finally {
      setLoading(false)
    }
  }, [activeTab, limit, preloadedData])

  // when allRecommendations is provided and tab changes, use those instead of fetching
  useEffect(() => {
    if (allRecommendations) {
      if (activeTab === 'friends') {
        setRecommendations(allRecommendations.friends || [])
      } else if (activeTab === 'similar') {
        setRecommendations(allRecommendations.similar || [])
      } else if (activeTab === 'lyrical') {
        setRecommendations(allRecommendations.lyrical || [])
      } else {
        setRecommendations(preloadedData || [])
      }
      setLoading(false)
      return
    }
    
    fetchRecommendations()
  }, [fetchRecommendations, activeTab, allRecommendations, preloadedData])

  const handleTabChange = (tab: 'hybrid' | 'friends' | 'similar' | 'lyrical') => {
    setActiveTab(tab)
  }

  const isDev = import.meta.env.DEV;
  const showScores = !hideScores && isDev;
  
  // debug mode (for testing purposes)
  const debugMode = false;

  return (
    <div className="w-full">
      {showTitle && (
        <div className="flex items-center justify-between mb-4 flex-wrap">
          <h2 className="text-xl font-bold text-white">recommended for you</h2>
          
          {!friendsOnly && !similarOnly && !lyricalOnly && (
            <div className="flex space-x-2 flex-wrap mt-2 sm:mt-0">
              <Button
                variant={activeTab === 'hybrid' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleTabChange('hybrid')}
                className="mb-1"
              >
                all
              </Button>
              <Button
                variant={activeTab === 'friends' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleTabChange('friends')}
                className="mb-1"
              >
                from friends
              </Button>
              <Button
                variant={activeTab === 'similar' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleTabChange('similar')}
                className="mb-1"
              >
                similar music
              </Button>
              <Button
                variant={activeTab === 'lyrical' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleTabChange('lyrical')}
                className="mb-1"
              >
                similar lyrics
              </Button>
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center items-center h-40">
          <Spinner size="lg" />
        </div>
      ) : error ? (
        <div className="text-center text-red-500 p-4 border border-red-700/50 bg-red-900/20 rounded-lg">
          {error}
        </div>
      ) : recommendations.length === 0 ? (
        <div className="text-center text-slate-400 py-8 border border-slate-700/50 bg-slate-800/20 rounded-lg">
          <p className="mb-2">no recommendations available</p>
          <p className="text-sm">try liking more songs to get personalized recommendations!</p>
        </div>
      ) : (
        <div className="space-y-2">
          {recommendations.map((song, index) => {
            // determine exactly which context we're in
            const isMainView = showTitle;
            const isFriendsTab = activeTab === 'friends';
            const isHybridTab = activeTab === 'hybrid';
            const isBottomFriendsPanel = !showTitle && friendsOnly;
            
            // parse and check if the song has friend data
            const friendsData = parseFriendsData(song.friends_who_like);
            const hasFriendData = friendsData !== null;
            
            // song is from friend recommendations in hybrid view
            const isFromFriendRecs = isHybridTab && song.recommendation_sources?.includes('friends');
            
            // debug info for troubleshooting
            if (debugMode) {
              console.log(`Song ${song.name}:`, {
                isMainView, 
                isFriendsTab, 
                isBottomFriendsPanel, 
                hasFriendData, 
                activeTab,
                friends_who_like: song.friends_who_like,
                friendsData,
                recommendation_sources: song.recommendation_sources
              });
            }

            return (
              <div key={song.id} className="relative bg-slate-800/30 hover:bg-slate-800/50 rounded-md transition-colors">
                <div className="grid grid-cols-1 gap-1">
                  <SongItem
                    song={{
                      id: song.id,
                      name: song.name,
                      artist: song.artist_names.split(', '),
                      album: song.album_name,
                      album_art_url: song.album_image_url,
                      spotify_uri: song.spotify_uri,
                      duration_ms: song.duration_ms || 0,
                      created_at: ''
                    }}
                    index={index}
                    playlistPublicId=""
                  />
                  
                  {/* CASE 1: show friend details in main Friends tab */}
                  {(isFriendsTab && isMainView && hasFriendData) && (
                    <div className="flex items-center ml-10 pb-2 text-xs text-slate-400 -mt-1">
                      <UserCircle className="h-3 w-3 mr-1 text-blue-500" />
                      <span className="truncate">liked by: {getFriendsNames(song.friends_who_like)}</span>
                    </div>
                  )}
                  
                  {/* CASE 2: show friend ax source in hybrid tab */}
                  {(isMainView && isHybridTab && isFromFriendRecs && hasFriendData) && (
                    <div className="flex items-center ml-10 pb-2 text-xs text-slate-400 -mt-1">
                      <UserCircle className="h-3 w-3 mr-1 text-blue-500" />
                      <span className="truncate">liked by: {getFriendsNames(song.friends_who_like)}</span>
                    </div>
                  )}
                  
                  {/* CASE 3: show generic source indicators in hybrid tab */}
                  {(isMainView && isHybridTab && song.recommendation_sources && 
                    !(isFromFriendRecs && hasFriendData)) && (
                    <div className="flex items-center ml-10 pb-2 text-xs text-slate-400 -mt-1">
                      {song.recommendation_sources.includes('friends') && (
                        <div className="flex items-center">
                          <UserCircle className="h-3 w-3 mr-1 text-blue-500" />
                          <span className="truncate">liked by friends</span>
                        </div>
                      )}
                      {song.recommendation_sources.includes('friends') && 
                        song.recommendation_sources.includes('similar_music') && 
                        <span className="mx-1">•</span>}
                      {song.recommendation_sources.includes('similar_music') && (
                        <div className="flex items-center">
                          <Disc className="h-3 w-3 mr-1 text-purple-500" />
                          <span className="truncate">similar to music you like</span>
                        </div>
                      )}
                    </div>
                  )}
                  
                  {/* only show similar/lyrical indicators in the main view and not in the bottom panels */}
                  {isMainView && (
                    <>
                      {activeTab === 'similar' && (
                        <div className="flex items-center ml-10 pb-2 text-xs text-slate-400 -mt-1">
                          <Disc className="h-3 w-3 mr-1 text-purple-500" />
                          <span className="truncate">similar to music you like</span>
                          {showScores && song.similarity_score !== undefined && (
                            <span className="ml-1 text-[10px] text-purple-400">(score: {song.similarity_score.toFixed(3)})</span>
                          )}
                        </div>
                      )}
                      
                      {activeTab === 'lyrical' && song.lyrics_similarity !== undefined && (
                        <div className="flex items-center ml-10 pb-2 text-xs text-slate-400 -mt-1">
                          <Mic className="h-3 w-3 mr-1 text-green-500" />
                          <span className="truncate">similar lyrical themes</span>
                          {showScores && (
                            <span className="ml-1 text-[10px] text-green-400">(score: {song.lyrics_similarity.toFixed(3)})</span>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  )
}

export default RecommendationsList 