import React from 'react';
import { useLoaderData } from 'react-router-dom';
import RecommendationsList from '../components/ui/recommendations-list';

// Import type from recommendations-list component or define it inline
type RecommendationSource = 'friends' | 'similar_music';

interface RecommendedSong {
  id: string;
  name: string;
  spotify_uri: string;
  spotify_url: string;
  popularity: number;
  album_name: string;
  album_image_url: string;
  artist_names: string;
  recommendation_score?: number;
  recommendation_sources?: RecommendationSource[];
  similarity_score?: number;
  friend_count?: number;
  friends_who_like?: Array<{
    friend_id: number;
    friend_name: string;
    friend_image: string;
  }>;
}

interface RecommendationsData {
  hybrid: RecommendedSong[];
  friends: RecommendedSong[];
  similar: RecommendedSong[];
  error?: string;
}

const RecommendationsPage: React.FC = () => {
  const { hybrid, friends, similar, error } = useLoaderData() as RecommendationsData;

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Music Recommendations</h1>
      
      {error && (
        <div className="bg-red-500 text-white p-4 mb-6 rounded-lg">
          {error}
        </div>
      )}
      
      <div className="grid grid-cols-1 gap-8">
        <div className="bg-gray-800 p-6 rounded-lg">
          <RecommendationsList 
            limit={20} 
            preloadedData={hybrid}
          />
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-gray-800 p-6 rounded-lg">
            <h2 className="text-2xl font-bold mb-4">From Your Friends</h2>
            <p className="text-gray-400 mb-4">
              Music that your friends have been enjoying recently.
            </p>
            <RecommendationsList 
              limit={10} 
              showTitle={false} 
              friendsOnly={true}
              preloadedData={friends}
            />
          </div>
          
          <div className="bg-gray-800 p-6 rounded-lg">
            <h2 className="text-2xl font-bold mb-4">Similar To What You Like</h2>
            <p className="text-gray-400 mb-4">
              Songs with similar audio characteristics to your liked music.
            </p>
            <RecommendationsList 
              limit={10} 
              showTitle={false} 
              similarOnly={true}
              preloadedData={similar}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default RecommendationsPage; 