import { useLoaderData, useNavigate } from "react-router-dom";
import { TubifyTitle } from "@/components/ui/tubify-title";
import { Button } from "@/components/ui/button";
import { Music, Heart, ArrowLeft } from "lucide-react";

interface UserProfileData {
  username: string;
  profilePicture: string;
  bio: string;
  playlistCount: number;
}

interface LikedSongsStats {
  friend_likes_count: number;
  shared_likes_count: number;
  user_likes_count: number;
  friend_unique_count: number;
  compatibility_percentage: number;
}

export default function UserProfile() {
  const { profile, likedSongsStats } = useLoaderData() as {
    profile: UserProfileData;
    likedSongsStats: LikedSongsStats | null;
  };
  const navigate = useNavigate();

  return (
    <div className="scrollable-page bg-linear-to-b from-slate-900 to-black">
      <div className="absolute top-0 left-0">
        <TubifyTitle />
      </div>
      <div className="flex items-center justify-center h-screen">
        <div className="mx-auto max-w-7xl w-full px-4 sm:px-6 lg:px-8">
          <div className="grid gap-6 md:grid-cols-3">
            {/* profile section - full width on mobile, 1/3 on desktop */}
            <div className="flex flex-col items-center bg-slate-800/60 border border-slate-700 rounded-xl p-5 relative">
              <img
                src={profile.profilePicture}
                alt={`${profile.username}'s profile`}
                className="w-24 h-24 md:w-32 md:h-32 rounded-full object-cover mb-4 border-2 border-slate-600"
              />

              <div className="flex flex-col items-center w-full h-full">
                <h2 className="text-white text-xl font-semibold">{profile.username}</h2>
                <div className="text-slate-400 text-center mt-2 mb-6 break-words whitespace-pre-wrap max-w-full">
                  {profile.bio || "No bio yet"}
                </div>
                <div className="mt-auto w-full">
                  <Button
                    onClick={() => navigate(-1)}
                    variant="outline"
                    className="w-full"
                  >
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back
                  </Button>
                </div>
              </div>
            </div>

            {/* content section - full width on mobile, 2/3 on desktop */}
            <div className="md:col-span-2 space-y-5">
              {/* music section */}
              <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-5">
                <h2 className="text-lg font-semibold text-white flex items-center mb-4">
                  <Music className="w-5 h-5 mr-2" />
                  Activity
                </h2>
                <div className="space-y-3">
                  <Button
                    onClick={() => navigate(`/users/${profile.username}/playlists`)}
                    variant="spotify"
                    className="w-full flex items-center justify-center"
                  >
                    <Music className="mr-2 h-4 w-4" />
                    View Playlists ({profile.playlistCount})
                  </Button>

                  {likedSongsStats && likedSongsStats.friend_likes_count > 0 && (
                    <>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <Button
                          onClick={() =>
                            navigate(`/users/${profile.username}/liked-songs`)
                          }
                          variant="outline"
                          className="bg-slate-700/50 border-slate-600 hover:bg-slate-700"
                        >
                          <Heart className="mr-2 h-4 w-4" />
                          Liked Songs ({likedSongsStats.friend_likes_count})
                        </Button>
                        
                        <Button
                          onClick={() =>
                            navigate(`/users/${profile.username}/reviews`)
                          }
                          variant="outline"
                          className="bg-slate-700/50 border-slate-600 hover:bg-slate-700"
                        >
                          <Heart className="mr-2 h-4 w-4" />
                          Reviews
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* compatibility section */}
              {likedSongsStats && likedSongsStats.friend_likes_count > 0 && (
                <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-5">
                  <h2 className="text-lg font-semibold text-white flex items-center mb-4">
                    <Heart className="w-5 h-5 mr-2" />
                    Music Compatibility
                  </h2>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex flex-col items-center p-3 bg-slate-700/50 rounded-lg border border-slate-600">
                      <span className="block text-slate-300 mb-1 text-sm">
                        Shared Songs
                      </span>
                      <span className="text-xl font-bold text-white">
                        {likedSongsStats.shared_likes_count}
                      </span>
                    </div>
                    <div className="flex flex-col items-center p-3 bg-slate-700/50 rounded-lg border border-slate-600">
                      <span className="block text-slate-300 mb-1 text-sm">
                        Compatibility
                      </span>
                      <span className="text-xl font-bold text-white">
                        {likedSongsStats.compatibility_percentage}%
                      </span>
                    </div>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-4">
                    <div className="flex flex-col items-center p-3 bg-slate-700/50 rounded-lg border border-slate-600">
                      <span className="block text-slate-300 mb-1 text-sm">
                        Your Liked Songs
                      </span>
                      <span className="text-xl font-bold text-white">
                        {likedSongsStats.user_likes_count}
                      </span>
                    </div>
                    <div className="flex flex-col items-center p-3 bg-slate-700/50 rounded-lg border border-slate-600">
                      <span className="block text-slate-300 mb-1 text-sm">
                        Their Unique Songs
                      </span>
                      <span className="text-xl font-bold text-white">
                        {likedSongsStats.friend_unique_count}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
