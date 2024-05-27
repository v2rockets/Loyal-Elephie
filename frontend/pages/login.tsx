import { useState } from 'react';
import { useRouter } from 'next/router';
import Cookies from 'js-cookie';

export default function Login() {
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const router = useRouter();

  // This function could be called after a successful login
  function handleLoginSuccess(token: string) {
    // Set the token in the cookie
    Cookies.set('Authorization', token, { expires: 30 }); // The cookie will expire after 30 days
    router.push('/');
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault(); // Prevent default form submission

    try {
      // Send a POST request to your server-side login API
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, password })
      });

      if (response.status === 200) {
        const { token } = await response.json();
        handleLoginSuccess(token); // Call the function to set the cookie
      } else {
        console.log('Login failed.');
        alert("Invalid login.")
      }
    } catch (error) {
      // Handle errors, such as displaying a login failure message to the user
      if (error instanceof Error) {
        console.error(error.message);
      } else {
        // If it's not an Error object, handle it as an unknown error
        console.error('An unknown error occurred');
      }
    }
  };

  return (
    <div className="flex flex-col items-center min-h-screen">
    <form onSubmit={handleLogin} className="my-1 rounded-lg px-2 sm:my-1.5 sm:p-4 sm:border border-neutral-300 justify-center">
      <div className="flex flex-col items-start">
        <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Username" required className="flex items-center bg-neutral-200 text-neutral-900 rounded-2xl px-3 py-2 max-w-[67%] whitespace-pre-wrap mb-4" />
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" required className="flex items-center bg-neutral-200 text-neutral-900 rounded-2xl px-3 py-2 max-w-[67%] whitespace-pre-wrap mb-4" />
        <button type="submit" className="flex items-center bg-blue-500 text-white rounded-2xl px-3 py-2 max-w-[67%] whitespace-pre-wrap">Login</button>
      </div>
    </form>
  </div>
  );
}