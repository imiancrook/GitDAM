'use client';

import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { Amplify } from 'aws-amplify';
import outputs from '@/amplify_outputs.json';
import GitDAMDashboard from '@/components/GitDAMDashboard';

Amplify.configure(outputs);

export default function Home() {
  return (
    <Authenticator>
      {({ signOut, user }) => (
        <div>
          <div style={{
            position: 'absolute',
            top: '20px',
            right: '20px',
            zIndex: 1000,
          }}>
            <span style={{ marginRight: '10px' }}>
              Signed in as: {user?.signInDetails?.loginId}
            </span>
            <button onClick={signOut} style={{
              padding: '8px 16px',
              background: '#dc3545',
              color: 'white',
              border: 'none',
              borderRadius: '5px',
              cursor: 'pointer',
            }}>
              Sign out
            </button>
          </div>
          <GitDAMDashboard />
        </div>
      )}
    </Authenticator>
  );
}
