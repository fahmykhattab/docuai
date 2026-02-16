import axios from 'axios';
import toast from 'react-hot-toast';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'An unexpected error occurred';

    if (error.response?.status === 404) {
      toast.error('Resource not found');
    } else if (error.response?.status === 422) {
      toast.error('Validation error: ' + message);
    } else if (error.response?.status >= 500) {
      toast.error('Server error: ' + message);
    } else if (error.code === 'ECONNABORTED') {
      toast.error('Request timed out');
    } else if (!error.response) {
      toast.error('Network error — is the server running?');
    }

    return Promise.reject(error);
  }
);

export default api;
