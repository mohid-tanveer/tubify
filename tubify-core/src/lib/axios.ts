import axios, { AxiosError } from "axios"

const api = axios.create({
  baseURL: "https://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
})

// add a request interceptor to handle CSRF token
api.interceptors.request.use(
  (config) => {
    // add CSRF token header if needed
    const csrfToken = document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrftoken="))
      ?.split("=")[1]
    if (csrfToken) {
      config.headers["X-CSRF-Token"] = csrfToken
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// add a response interceptor to handle unauthorized responses
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // if the error is 401 and we haven't already tried to refresh
    // and the request isn't for refresh, auth/me, login, or register
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/refresh") &&
      !originalRequest.url?.includes("/auth/me") &&
      !originalRequest.url?.includes("/auth/login") &&
      !originalRequest.url?.includes("/auth/register")
    ) {
      originalRequest._retry = true

      try {
        // attempt to refresh the token
        await api.post("/api/auth/refresh")

        // retry the original request
        return api(originalRequest)
      } catch (refreshError) {
        // if refresh fails, don't redirect if we're already on the auth page
        if (!window.location.pathname.includes("/auth")) {
          window.location.href = "/auth"
        }
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  },
)

export default api
export { AxiosError }
