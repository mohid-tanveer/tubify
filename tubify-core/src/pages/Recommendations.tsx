import React from 'react';
import { useLoaderData, useNavigate } from 'react-router-dom';
import RecommendationsList from '../components/ui/recommendations-list';
import { TubifyTitle } from '../components/ui/tubify-title';
import { Button } from '../components/ui/button';
import { ArrowLeft } from 'lucide-react';

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
  lyrics_similarity?: number;
  friend_count?: number;
  friends_who_like?: Array<{
    friend_id: number;
    friend_name: string;
    friend_image: string;
  }>;
  duration_ms?: number;
}

interface RecommendationsData {
  hybrid: RecommendedSong[];
  friends: RecommendedSong[];
  similar: RecommendedSong[];
  lyrical: RecommendedSong[];
  error?: string;
}

const RecommendationsPage: React.FC = () => {
  const { hybrid, friends, similar, lyrical, error } = useLoaderData() as RecommendationsData;
  const navigate = useNavigate();

  return (
    <div className="scrollable-page bg-gradient-to-b from-slate-900 to-black min-h-screen">
      <div className="absolute top-4 left-4 z-10">
        <TubifyTitle />
      </div>
      
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-24">
        <div className="pt-6 pb-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/")}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            back
          </Button>
        </div>

        <div className="mb-8">
          <h1 className="text-2xl md:text-3xl font-bold text-white">music recommendations</h1>
          <p className="mt-2 text-slate-400">personalized music recommendations based on your taste</p>
        </div>
        
        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-700 rounded-lg text-white">
            {error}
          </div>
        )}
        
        <div className="grid gap-6 pb-8">
          <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-lg hover:border-slate-700 transition-colors">
            <h2 className="text-xl font-bold text-white mb-4">for you</h2>
            <p className="text-slate-400 mb-4">
              curated recommendations based on your listening habits and friends
            </p>
            <RecommendationsList 
              limit={20} 
              preloadedData={hybrid}
              allRecommendations={{
                friends: friends,
                similar: similar,
                lyrical: lyrical
              }}
              showFriendIndicators={true}
            />
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-lg hover:border-slate-700 transition-colors">
              <h2 className="text-xl font-bold text-white mb-4">from your friends</h2>
              <p className="text-slate-400 mb-4">
                music that your friends have been enjoying recently
              </p>
              <RecommendationsList 
                limit={10} 
                showTitle={false} 
                friendsOnly={true}
                preloadedData={friends}
                hideScores={true}
              />
            </div>
            
            <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-lg hover:border-slate-700 transition-colors">
              <h2 className="text-xl font-bold text-white mb-4">similar to what you like</h2>
              <p className="text-slate-400 mb-4">
                songs with similar audio characteristics to your liked music
              </p>
              <RecommendationsList 
                limit={10} 
                showTitle={false} 
                similarOnly={true}
                preloadedData={similar}
                hideScores={true}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RecommendationsPage; 