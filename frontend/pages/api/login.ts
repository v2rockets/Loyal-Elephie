import type { NextApiRequest, NextApiResponse } from 'next';
import jwt from 'jsonwebtoken';
import users from '../../users.json'; // Assuming users.json is at the root of your project

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method === 'POST') {
    const { username, password } = req.body;

    // Find the user in the users.json file
    const user = users.find((u: any) => u.username === username && u.password === password);

    if (user) {
      // For security purposes, don't send back the password
      const { password, ...userWithoutPassword } = user;

      console.log(userWithoutPassword)
      // Generate a JWT for the user
      const token = jwt.sign(userWithoutPassword, 'shared_key', { expiresIn: '30d' });

      // Send back a success response with the user data (excluding the password) and the token
      res.status(200).json({ user: userWithoutPassword, token });
    } else {
      // If the user is not found, send back an error response
      res.status(401).json({ message: 'Invalid credentials' });
    }
  } else {
    // If the request is not a POST request, send back an error response
    res.setHeader('Allow', ['POST']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}