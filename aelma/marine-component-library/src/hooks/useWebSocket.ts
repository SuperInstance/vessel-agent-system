/**
 * WebSocket integration hook for marine digital twin
 * Provides real-time vessel state updates with automatic reconnection
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { VesselStateSnapshot, WebSocketMessage } from '../types/vessel';

export interface UseWebSocketOptions {
  url: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  onMessage?: (message: WebSocketMessage) => void;
  onError?: (error: Event) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  enabled?: boolean;
}

export interface UseWebSocketReturn {
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  reconnectAttempts: number;
  sendMessage: (message: unknown) => void;
  connect: () => void;
  disconnect: () => void;
  manualReconnect: () => void;
}

/**
 * WebSocket hook for marine digital twin connection
 */
export function useWebSocket(
  options: UseWebSocketOptions
): UseWebSocketReturn {
  const {
    url,
    reconnectInterval = 1000,
    maxReconnectAttempts = 5,
    onMessage,
    onError,
    onConnect,
    onDisconnect,
    enabled = true,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const manualCloseRef = useRef(false);

  /**
   * Clear reconnect timeout
   */
  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  /**
   * Schedule reconnect
   */
  const scheduleReconnect = useCallback(() => {
    if (manualCloseRef.current) return;

    clearReconnectTimeout();

    if (reconnectAttempts >= maxReconnectAttempts) {
      setError(`Max reconnect attempts (${maxReconnectAttempts}) reached`);
      setIsConnecting(false);
      return;
    }

    setIsConnecting(true);
    setError(`Reconnecting in ${reconnectInterval / 1000}s... (attempt ${reconnectAttempts + 1}/${maxReconnectAttempts})`);

    reconnectTimeoutRef.current = setTimeout(() => {
      setReconnectAttempts(prev => prev + 1);
      connect();
    }, reconnectInterval);
  }, [reconnectInterval, maxReconnectAttempts, reconnectAttempts, clearReconnectTimeout]);

  /**
   * Connect to WebSocket
   */
  const connect = useCallback(() => {
    if (!enabled) return;

    clearReconnectTimeout();

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      setIsConnected(true);
      return;
    }

    setIsConnecting(true);
    setError(null);

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setIsConnecting(false);
        setError(null);
        setReconnectAttempts(0);
        if (onConnect) onConnect();
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage;
          if (onMessage) onMessage(message);
        } catch (err) {
          console.error('[useWebSocket] Failed to parse message:', err);
        }
      };

      ws.onerror = (event: Event) => {
        setError('WebSocket error occurred');
        if (onError) onError(event);
      };

      ws.onclose = () => {
        setIsConnected(false);
        setIsConnecting(false);
        if (onDisconnect) onDisconnect();

        if (!manualCloseRef.current) {
          scheduleReconnect();
        }
      };
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown connection error';
      setError(message);
      setIsConnecting(false);
      scheduleReconnect();
    }
  }, [url, enabled, onMessage, onError, onConnect, onDisconnect, scheduleReconnect, clearReconnectTimeout]);

  /**
   * Disconnect from WebSocket
   */
  const disconnect = useCallback(() => {
    manualCloseRef.current = true;
    clearReconnectTimeout();

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
    setIsConnecting(false);
    setReconnectAttempts(0);
  }, [clearReconnectTimeout]);

  /**
   * Manual reconnect
   */
  const manualReconnect = useCallback(() => {
    manualCloseRef.current = false;
    setReconnectAttempts(0);
    setError(null);
    connect();
  }, [connect]);

  /**
   * Send message through WebSocket
   */
  const sendMessage = useCallback((message: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('[useWebSocket] Cannot send message - WebSocket not connected');
    }
  }, []);

  /**
   * Auto-connect on mount
   */
  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [enabled]); // Only run on enabled change

  return {
    isConnected,
    isConnecting,
    error,
    reconnectAttempts,
    sendMessage,
    connect,
    disconnect,
    manualReconnect,
  };
}

/**
 * Hook for vessel state updates
 */
export interface UseVesselStateOptions extends UseWebSocketOptions {
  enabled?: boolean;
}

export interface UseVesselStateReturn {
  vesselState: VesselStateSnapshot | null;
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  reconnectAttempts: number;
  sendMessage: (message: unknown) => void;
  connect: () => void;
  disconnect: () => void;
  manualReconnect: () => void;
}

export function useVesselState(
  url: string,
  options: Omit<UseVesselStateOptions, 'url'>
): UseVesselStateReturn {
  const [vesselState, setVesselState] = useState<VesselStateSnapshot | null>(null);

  const handleMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === 'snapshot' && message.data) {
      setVesselState(message.data as VesselStateSnapshot);
    }
  }, []);

  const wsHook = useWebSocket({
    ...options,
    url,
    onMessage: handleMessage,
  });

  return {
    ...wsHook,
    vesselState,
  };
}

/**
 * Hook for action events
 */
export interface UseActionEventsOptions extends UseWebSocketOptions {
  enabled?: boolean;
}

export interface UseActionEventsReturn {
  actions: ActionEvent[];
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  reconnectAttempts: number;
  sendMessage: (message: unknown) => void;
  connect: () => void;
  disconnect: () => void;
  manualReconnect: () => void;
  clearActions: () => void;
}

interface ActionEvent {
  action: string;
  payload?: Record<string, unknown>;
  reason?: string;
  priority: number;
  rule_id?: string;
  timestamp_ns: bigint;
}

export function useActionEvents(
  url: string,
  options: Omit<UseActionEventsOptions, 'url'>
): UseActionEventsReturn {
  const [actions, setActions] = useState<ActionEvent[]>([]);

  const handleMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === 'action' && message.data) {
      setActions(prev => [...prev, message.data as ActionEvent]);
    }
  }, []);

  const wsHook = useWebSocket({
    ...options,
    url,
    onMessage: handleMessage,
  });

  const clearActions = useCallback(() => {
    setActions([]);
  }, []);

  return {
    ...wsHook,
    actions,
    clearActions,
  };
}

/**
 * Hook for offline-first data sync
 */
export interface UseOfflineSyncOptions<T> {
  storageKey: string;
  enabled?: boolean;
  syncInterval?: number;
  maxStoredItems?: number;
}

export interface UseOfflineSyncReturn<T> {
  items: T[];
  addItem: (item: T) => void;
  clearItems: () => void;
  isOnline: boolean;
  syncStatus: 'synced' | 'syncing' | 'offline' | 'error';
  forceSync: () => void;
}

export function useOfflineSync<T extends { id: string }>(
  wsUrl: string,
  options: UseOfflineSyncOptions<T>
): UseOfflineSyncReturn<T> {
  const [items, setItems] = useState<T[]>([]);
  const [isOnline, setIsOnline] = useState(true);
  const [syncStatus, setSyncStatus] = useState<'synced' | 'syncing' | 'offline' | 'error'>('synced');

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(options.storageKey);
      if (stored) {
        const parsed = JSON.parse(stored) as T[];
        setItems(parsed.slice(0, options.maxStoredItems || 1000));
      }
    } catch (err) {
      console.error('[useOfflineSync] Failed to load from storage:', err);
    }
  }, [options.storageKey, options.maxStoredItems]);

  // Monitor online status
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Update sync status based on online status
  useEffect(() => {
    if (isOnline) {
      setSyncStatus('synced');
    } else {
      setSyncStatus('offline');
    }
  }, [isOnline]);

  // Save to localStorage when items change
  useEffect(() => {
    try {
      const sliced = items.slice(0, options.maxStoredItems || 1000);
      localStorage.setItem(options.storageKey, JSON.stringify(sliced));
    } catch (err) {
      console.error('[useOfflineSync] Failed to save to storage:', err);
      setSyncStatus('error');
    }
  }, [items, options.storageKey, options.maxStoredItems]);

  const addItem = useCallback((item: T) => {
    setItems(prev => [...prev, item]);
  }, []);

  const clearItems = useCallback(() => {
    setItems([]);
    localStorage.removeItem(options.storageKey);
  }, [options.storageKey]);

  const forceSync = useCallback(() => {
    setSyncStatus('syncing');
    // In a real implementation, this would sync with the server
    setTimeout(() => {
      setSyncStatus('synced');
    }, 1000);
  }, []);

  return {
    items,
    addItem,
    clearItems,
    isOnline,
    syncStatus,
    forceSync,
  };
}

export default useWebSocket;
