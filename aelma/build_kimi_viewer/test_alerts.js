/**
 * Test script for Alerts UI
 * Run this in the browser console to test the alert system
 */

// Test data
const testAlerts = [
  {
    name: 'Critical Grounding Risk',
    data: {
      action: 'raise_alert',
      payload: {
        severity: 'critical',
        code: 'GROUNDING_RISK',
        message: 'GROUNDING RISK: depth=0.8m'
      },
      reason: 'depth=0.80m',
      priority: 0.95,
      rule_id: 'grounding-risk',
      timestamp_ns: BigInt(Date.now() * 1e6).toString()
    }
  },
  {
    name: 'Engine Overheat',
    data: {
      action: 'raise_alert',
      payload: {
        severity: 'critical',
        code: 'ENGINE_OVERHEAT',
        message: 'Engine overheat: 95.0°C'
      },
      reason: 'engine_temp=95.0°C',
      priority: 0.92,
      rule_id: 'engine-overheat',
      timestamp_ns: BigInt(Date.now() * 1e6).toString()
    }
  },
  {
    name: 'Shallow Water Warning',
    data: {
      action: 'raise_alert',
      payload: {
        severity: 'warning',
        code: 'SHALLOW_WATER',
        message: 'Depth critical: 1.5m'
      },
      reason: 'depth=1.50m',
      priority: 0.85,
      rule_id: 'shallow-water',
      timestamp_ns: BigInt(Date.now() * 1e6).toString()
    }
  },
  {
    name: 'Medium Priority Alert',
    data: {
      action: 'raise_alert',
      payload: {
        severity: 'info',
        code: 'DEPTH_WARNING',
        message: 'Depth below 5m'
      },
      reason: 'depth=4.80m',
      priority: 0.6,
      rule_id: 'depth-warning',
      timestamp_ns: BigInt(Date.now() * 1e6).toString()
    }
  },
  {
    name: 'Low Priority Alert',
    data: {
      action: 'raise_alert',
      payload: {
        severity: 'info',
        code: 'DEPTH_LOW',
        message: 'Depth decreasing'
      },
      reason: 'depth=8.20m',
      priority: 0.3,
      rule_id: 'depth-low',
      timestamp_ns: BigInt(Date.now() * 1e6).toString()
    }
  }
];

// Function to send alert via WebSocket
function sendTestAlert(alertData) {
  if (typeof window.handleActionEvent === 'function') {
    // Direct call to the handler
    window.handleActionEvent(alertData);
    console.log('[Test] Sent alert via direct call:', alertData);
  } else {
    console.error('[Test] handleActionEvent not found - viewer not loaded?');
  }
}

// Run all tests
function runAllTests() {
  console.log('[Test] Running all alert tests...');
  testAlerts.forEach((test, index) => {
    setTimeout(() => {
      console.log(`[Test] ${index + 1}. ${test.name}`);
      sendTestAlert(test.data);
    }, index * 1000);
  });
}

// Test clear alerts
function testClearAlerts() {
  console.log('[Test] Testing clear_alerts...');
  if (typeof window.clearAllAlerts === 'function') {
    window.clearAllAlerts();
    console.log('[Test] Cleared all alerts');
  } else {
    console.error('[Test] clearAllAlerts not found');
  }
}

// Test individual alerts
function testCriticalAlert() {
  console.log('[Test] Testing critical alert...');
  sendTestAlert(testAlerts[0].data);
}

function testHighAlert() {
  console.log('[Test] Testing high priority alert...');
  sendTestAlert(testAlerts[2].data);
}

function testMediumAlert() {
  console.log('[Test] Testing medium priority alert...');
  sendTestAlert(testAlerts[3].data);
}

function testLowAlert() {
  console.log '[Test] Testing low priority alert...');
  sendTestAlert(testAlerts[4].data);
}

// Export for browser console
window.testAlerts = {
  runAll: runAllTests,
  clear: testClearAlerts,
  critical: testCriticalAlert,
  high: testHighAlert,
  medium: testMediumAlert,
  low: testLowAlert,
  send: sendTestAlert
};

console.log('[Test] Alert test functions loaded. Usage:');
console.log('  testAlerts.runAll() - Run all tests');
console.log('  testAlerts.critical() - Test critical alert');
console.log('  testAlerts.high() - Test high priority alert');
console.log('  testAlerts.medium() - Test medium priority alert');
console.log('  testAlerts.low() - Test low priority alert');
console.log('  testAlerts.clear() - Clear all alerts');
