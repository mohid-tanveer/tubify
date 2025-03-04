import { useContext, useEffect, useState } from "react";
import { AuthContext } from "@/contexts/auth";
import { TubifyTitle } from "@/components/ui/tubify-title";
import api from "@/lib/axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { z } from "zod";
import axios from "axios";

const profileSchema = z.object({
  username: z
    .string()
    .min(3, "username must be at least 3 characters")
    .max(50, "username must be less than 50 characters")
    .regex(
      /^[a-zA-Z0-9._-]+$/,
      "username can only contain letters, numbers, periods, underscores, and hyphens"
    ),
  bio: z.string().max(500, "bio must be less than 500 characters"),
});

interface Profile {
  user_name: string;
  profile_picture: string;
  bio: string;
}

interface Friend {
  id: number;
  username: string;
  profile_picture: string;
}

interface FriendRequest {
  sender_id: number;
  receiver_id: number;
  status: string;
  username: string; // Add the username field
}

export default function Profile() {
  const { isAuthenticated, logout } = useContext(AuthContext);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [friends, setFriends] = useState<Friend[]>([]);
  const [friendRequests, setFriendRequests] = useState<FriendRequest[]>([]);
  const [searchUsername, setSearchUsername] = useState("");
  const [isAddingFriend, setIsAddingFriend] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      fetchProfile();
      fetchFriends();
      fetchFriendRequests();
    }
  }, [isAuthenticated]);

  const fetchProfile = async () => {
    try {
      setIsLoading(true);
      const response = await api.get("/api/profile");
      setProfile(response.data);
    } catch (error) {
      console.error("failed to fetch profile:", error);
      toast.error("Failed to load profile");
    } finally {
      setIsLoading(false);
    }
  };

  const fetchFriends = async () => {
    try {
      const response = await api.get("/api/profile/friends");
      setFriends(response.data);
      console.log(response.data);
    } catch (error) {
      console.error("failed to fetch friends:", error);
    }
  };

  const fetchFriendRequests = async () => {
    try {
      const response = await api.get("/api/profile/friend-requests");
      setFriendRequests(response.data);
    } catch (error) {
      console.error("failed to fetch friend requests:", error);
    }
  };

  const handleAddFriend = async () => {
    try {
      setIsAddingFriend(true);
      await api.post(`/api/profile/add-friend/${searchUsername}`);
      toast.success("Friend request sent!");
      setSearchUsername("");
      fetchFriendRequests();
    } catch (error) {
      console.error("failed to add friend:", error);
      if (
        axios.isAxiosError(error) &&
        error.response &&
        error.response.data &&
        error.response.data.detail
      ) {
        toast.error(error.response.data.detail);
      } else {
        toast.error("Failed to send friend request.");
      }
    } finally {
      setIsAddingFriend(false);
    }
  };

  const handleAcceptFriendRequest = async (senderId: number) => {
    try {
      await api.post(`/api/profile/accept-friend-request/${senderId}`);
      toast.success("Friend request accepted!");
      fetchFriends();
      fetchFriendRequests();
    } catch (error) {
      console.error("failed to accept friend request:", error);
      toast.error("Failed to accept friend request.");
    }
  };

  const handleRemoveFriend = async (friendId: number) => {
    try {
      await api.post(`/api/profile/remove-friend/${friendId}`);
      toast.success("Friend removed!");
      fetchFriends();
    } catch (error) {
      console.error("failed to remove friend:", error);
      toast.error("Failed to remove friend.");
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="overflow-hidden flex flex-col min-h-screen">
        <div className="absolute top-0 left-0">
          <TubifyTitle />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-white">Please sign in to view your profile.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden flex flex-col min-h-screen">
      <div className="absolute top-0 left-0">
        <TubifyTitle />
      </div>
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          {isLoading ? (
            <p className="text-white">Loading...</p>
          ) : (
            profile && (
              <>
                <img
                  src={profile.profile_picture}
                  alt={`${profile.user_name}'s profile`}
                  className="w-32 h-32 rounded-full"
                />
                <h2 className="text-white text-2xl">{profile.user_name}</h2>
                <p className="text-white">{profile.bio}</p>
                <Button
                  onClick={logout}
                  className="text-white hover:text-red-500 transition-colors"
                >
                  Sign out
                </Button>
                <div className="flex flex-col items-center gap-4">
                  <h2 className="text-white text-xl">Friends</h2>
                  <ul className="text-white">
                    {friends.map((friend) => (
                      <li key={friend.id} className="flex items-center gap-2">
                        <img
                          src={friend.profile_picture}
                          alt={friend.username}
                          className="w-8 h-8 rounded-full"
                        />
                        <span>{friend.username}</span>
                        <Button
                          onClick={() => handleRemoveFriend(friend.id)}
                          className="text-red-500 hover:text-red-700 transition-colors"
                        >
                          Remove
                        </Button>
                      </li>
                    ))}
                  </ul>
                  <h2 className="text-white text-xl">Friend Requests</h2>
                  <ul className="text-white">
                    {friendRequests.map((request) => (
                      <li
                        key={request.sender_id}
                        className="flex items-center gap-2"
                      >
                        <span>{request.username}</span>{" "}
                        {/* Display the username */}
                        <Button
                          onClick={() =>
                            handleAcceptFriendRequest(request.sender_id)
                          }
                          className="text-green-500 hover:text-green-700 transition-colors"
                        >
                          Accept
                        </Button>
                      </li>
                    ))}
                  </ul>
                  <div className="flex items-center gap-2">
                    <Input
                      value={searchUsername}
                      onChange={(e) => setSearchUsername(e.target.value)}
                      placeholder="Search username"
                      className="text-black"
                    />
                    <Button
                      onClick={handleAddFriend}
                      disabled={isAddingFriend}
                      className="text-white hover:text-blue-500 transition-colors"
                    >
                      Add Friend
                    </Button>
                  </div>
                </div>
              </>
            )
          )}
        </div>
      </div>
    </div>
  );
}
