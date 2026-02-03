/**
 * Hook for managing push notifications in Silicon Casino PWA.
 *
 * Provides functionality to:
 * - Check if push notifications are supported
 * - Request notification permission
 * - Subscribe to push notifications
 * - Manage notification preferences
 */

import { useState, useEffect, useCallback } from "react";
import { useStore } from "../store";

interface PushSubscriptionKeys {
  p256dh: string;
  auth: string;
}

interface NotificationPreferences {
  bigHands: boolean;
  tournamentStart: boolean;
  challengeResults: boolean;
  referralEarnings: boolean;
}

interface UsePushNotificationsReturn {
  isSupported: boolean;
  permission: NotificationPermission;
  isSubscribed: boolean;
  isLoading: boolean;
  error: string | null;
  subscribe: () => Promise<boolean>;
  unsubscribe: () => Promise<boolean>;
  updatePreferences: (prefs: Partial<NotificationPreferences>) => Promise<boolean>;
  preferences: NotificationPreferences;
}

const DEFAULT_PREFERENCES: NotificationPreferences = {
  bigHands: true,
  tournamentStart: true,
  challengeResults: true,
  referralEarnings: true,
};

export function usePushNotifications(): UsePushNotificationsReturn {
  const { token } = useStore();
  const [isSupported, setIsSupported] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission>("default");
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preferences, setPreferences] = useState<NotificationPreferences>(DEFAULT_PREFERENCES);

  // Check support on mount
  useEffect(() => {
    const supported =
      "serviceWorker" in navigator &&
      "PushManager" in window &&
      "Notification" in window;
    setIsSupported(supported);

    if (supported) {
      setPermission(Notification.permission);
      checkSubscription();
      loadPreferences();
    }
  }, []);

  const checkSubscription = async () => {
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      setIsSubscribed(!!subscription);
    } catch (err) {
      console.error("Error checking subscription:", err);
    }
  };

  const loadPreferences = async () => {
    if (!token) return;

    try {
      const response = await fetch("/api/notifications/preferences", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setPreferences({
          bigHands: data.big_hands ?? true,
          tournamentStart: data.tournament_start ?? true,
          challengeResults: data.challenge_results ?? true,
          referralEarnings: data.referral_earnings ?? true,
        });
      }
    } catch (err) {
      console.error("Error loading preferences:", err);
    }
  };

  const subscribe = useCallback(async (): Promise<boolean> => {
    if (!isSupported || !token) {
      setError("Push notifications not supported or not logged in");
      return false;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Request permission
      const perm = await Notification.requestPermission();
      setPermission(perm);

      if (perm !== "granted") {
        setError("Notification permission denied");
        return false;
      }

      // Get service worker registration
      const registration = await navigator.serviceWorker.ready;

      // Get VAPID public key from server
      const vapidResponse = await fetch("/api/notifications/vapid-key");
      if (!vapidResponse.ok) {
        throw new Error("Failed to get VAPID key");
      }
      const { publicKey } = await vapidResponse.json();

      // Subscribe to push
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      });

      // Extract keys
      const subscriptionJson = subscription.toJSON();
      const keys = subscriptionJson.keys as PushSubscriptionKeys;

      // Send subscription to server
      const response = await fetch("/api/notifications/subscribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          endpoint: subscription.endpoint,
          p256dh_key: keys.p256dh,
          auth_key: keys.auth,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to save subscription");
      }

      setIsSubscribed(true);
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      console.error("Push subscription error:", err);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [isSupported, token]);

  const unsubscribe = useCallback(async (): Promise<boolean> => {
    if (!isSupported || !token) {
      return false;
    }

    setIsLoading(true);
    setError(null);

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();

      if (subscription) {
        // Unsubscribe from push manager
        await subscription.unsubscribe();

        // Remove from server
        await fetch("/api/notifications/unsubscribe", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            endpoint: subscription.endpoint,
          }),
        });
      }

      setIsSubscribed(false);
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      console.error("Push unsubscribe error:", err);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [isSupported, token]);

  const updatePreferences = useCallback(
    async (prefs: Partial<NotificationPreferences>): Promise<boolean> => {
      if (!token) return false;

      setIsLoading(true);
      setError(null);

      try {
        const newPrefs = { ...preferences, ...prefs };

        const response = await fetch("/api/notifications/preferences", {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            big_hands: newPrefs.bigHands,
            tournament_start: newPrefs.tournamentStart,
            challenge_results: newPrefs.challengeResults,
            referral_earnings: newPrefs.referralEarnings,
          }),
        });

        if (!response.ok) {
          throw new Error("Failed to update preferences");
        }

        setPreferences(newPrefs);
        return true;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
        console.error("Preferences update error:", err);
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [token, preferences]
  );

  return {
    isSupported,
    permission,
    isSubscribed,
    isLoading,
    error,
    subscribe,
    unsubscribe,
    updatePreferences,
    preferences,
  };
}

// Helper to convert VAPID key
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export default usePushNotifications;
