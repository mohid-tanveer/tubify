import { useState } from "react";
import { TubifyTitle } from "@/components/ui/tubify-title";

export default function Search() {
    const [searchQuery, setSearchQuery] = useState("");

    const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setSearchQuery(event.target.value);
    };

  return (
    <div className="h-screen bg-gradient-to-b from-gray-950 to-gray-700">
      <div className="overflow-hidden flex flex-col min-h-screen">
        <div className="absolute top-0 left-0">
          <TubifyTitle />
        </div>

        <div className="flex flex-col items-center gap-40">
            <h1 className="text-white text-2xl tracking-normal py-10">Search</h1>
        </div>

        <div className="flex-1 flex items-top justify-center">
          <div className="flex flex-col items-center gap-4">
            <form>
              <div className="mb-6">
                <label
                  htmlFor="searchQuery"
                  className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                >
                 
                </label>
                <input
                  type="text"
                  id="searchQuery"
                  value = {searchQuery}
                  onChange={handleInputChange}
                  className="block w-full p-3 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 text-base focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                />
              </div>
            </form>

            <div className="w-full">
                <h2 className="text-white text-xl">Results:</h2>
                <div className="mt-4">
                    {searchQuery && (
                        <div className="bg-gray800 p-4 rounded-lg text-white">
                            <p>Search Query: {searchQuery}</p>
                        </div>
                    )}
                </div>

            </div>

          </div>
        </div>
      </div>
    </div>
  );
}