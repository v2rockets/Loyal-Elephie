import type { NextApiRequest, NextApiResponse } from 'next';
import jwt from 'jsonwebtoken';
import { parse } from 'cookie';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method === 'GET') {
    const cookies = req.headers.cookie ? parse(req.headers.cookie) : {};
    // Now you can access the cookies like this:
    const token = cookies["Authorization"];
    // const token = req.headers.authorization?.split(' ')[1]; // Bearer Token

    if (token) {
      try {
        // Verify the token
        const decoded = jwt.verify(token, 'shared_key');
        res.status(200).json({ message: 'This is a secure message'});
      } catch (error) {
        res.status(401).json({ message: 'Unauthorized or token expired' });
      }
    } else {
      res.status(401).json({ message: 'No token provided' });
    }
  } else {
    res.status(405).json({ message: 'We only accept GET' });
  }
}