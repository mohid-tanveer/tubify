import React, { useState, useEffect, useCallback } from 'react'
import api from '@/lib/axios'
import { Button } from './button'
import { Spinner } from './spinner'
import { SongItem } from './song-item'

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
}

interface RecommendationsListProps {
  limit?: number
  showTitle?: boolean
  friendsOnly?: boolean
  similarOnly?: boolean
  lyricalOnly?: boolean
  preloadedData?: RecommendedSong[]
}

const RecommendationsList: React.FC<RecommendationsListProps> = ({
  limit = 10,
  showTitle = true,
  friendsOnly = false,
  similarOnly = false,
  lyricalOnly = false,
  preloadedData
}) => {
  const [recommendations, setRecommendations] = useState<RecommendedSong[]>(preloadedData || [])
  const [loading, setLoading] = useState<boolean>(!preloadedData)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'hybrid' | 'friends' | 'similar' | 'lyrical'>(
    friendsOnly ? 'friends' : similarOnly ? 'similar' : lyricalOnly ? 'lyrical' : 'hybrid'
  )

  const fetchRecommendations = useCallback(async () => {
    // Skip fetching if preloaded data is provided
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

  useEffect(() => {
    fetchRecommendations()
  }, [fetchRecommendations])

  const handleTabChange = (tab: 'hybrid' | 'friends' | 'similar' | 'lyrical') => {
    setActiveTab(tab)
  }

  return (
    <div className="w-full">
      {showTitle && (
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">Recommended For You</h2>
          
          {!friendsOnly && !similarOnly && !lyricalOnly && (
            <div className="flex space-x-2 flex-wrap">
              <Button
                variant={activeTab === 'hybrid' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleTabChange('hybrid')}
                className="mb-1"
              >
                All
              </Button>
              <Button
                variant={activeTab === 'friends' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleTabChange('friends')}
                className="mb-1"
              >
                From Friends
              </Button>
              <Button
                variant={activeTab === 'similar' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleTabChange('similar')}
                className="mb-1"
              >
                Similar Music
              </Button>
              <Button
                variant={activeTab === 'lyrical' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleTabChange('lyrical')}
                className="mb-1"
              >
                Similar Lyrics
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
        <div className="text-center text-red-500 py-4">{error}</div>
      ) : recommendations.length === 0 ? (
        <div className="text-center text-gray-500 py-4">
          No recommendations available. Try liking more songs!
        </div>
      ) : (
        <div className="space-y-2">
          {recommendations.map((song, index) => (
            <div key={song.id} className="relative">
              <SongItem
                song={{
                  id: song.id,
                  name: song.name,
                  artist: song.artist_names.split(', '),
                  album: song.album_name,
                  album_art_url: song.album_image_url,
                  spotify_uri: song.spotify_uri,
                  duration_ms: 0,
                  created_at: ''
                }}
                index={index}
                playlistPublicId=""
              />
              
              {activeTab === 'friends' && song.friends_who_like && song.friends_who_like.length > 0 && (
                <div className="mt-1 ml-12 text-xs text-gray-500">
                  Liked by: {song.friends_who_like.map(f => f.friend_name).join(', ')}
                </div>
              )}
              
              {activeTab === 'hybrid' && song.recommendation_sources && (
                <div className="mt-1 ml-12 text-xs text-gray-500">
                  {song.recommendation_sources.includes('friends') && 'Liked by friends'}
                  {song.recommendation_sources.includes('friends') && 
                   song.recommendation_sources.includes('similar_music') && ' • '}
                  {song.recommendation_sources.includes('similar_music') && 'Similar to music you like'}
                </div>
              )}
              
              {activeTab === 'lyrical' && song.lyrics_similarity !== undefined && (
                <div className="mt-1 ml-12 text-xs text-gray-500">
                  Similar lyrical themes to songs you like
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default RecommendationsList 