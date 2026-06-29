import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  clearBecasSession,
  getStoredBecasUser,
  loginBecas,
} from '../services/becasApi';

const AuthContext = createContext({});

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const stored = await getStoredBecasUser();
        if (mounted) setUser(stored);
      } catch {
        if (mounted) setUser(null);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const login = async (username, password) => {
    try {
      const nextUser = await loginBecas({ username, password });
      setUser(nextUser);
      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error?.message || 'No se pudo iniciar sesion.',
      };
    }
  };

  const logout = async () => {
    await clearBecasSession();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: !!user,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
