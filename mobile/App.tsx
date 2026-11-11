import React, { useRef, useState } from 'react';
import { ActivityIndicator, BackHandler, SafeAreaView, StatusBar, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { WebView } from 'react-native-webview';

const { APP_HOME, isTrustedUrl } = require('./security');
const APP_ORIGIN = 'https://learningmanagementsystem.pythonanywhere.com';

/**
 * Connected mobile foundation. The website owns authentication, school
 * permissions and records; this app never stores credentials or school data.
 * Native screens will replace this authenticated WebView progressively.
 */
export default function App() {
  const browser = useRef<WebView>(null);
  const [canGoBack, setCanGoBack] = useState(false);
  const [loading, setLoading] = useState(true);

  React.useEffect(() => {
    const listener = BackHandler.addEventListener('hardwareBackPress', () => {
      if (!canGoBack) return false;
      browser.current?.goBack();
      return true;
    });
    return () => listener.remove();
  }, [canGoBack]);

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#133b73" />
      <View style={styles.header}>
        <Text style={styles.brand}>Nexus School</Text>
        <TouchableOpacity accessibilityRole="button" accessibilityLabel="Return to portal home" onPress={() => browser.current?.injectJavaScript(`window.location.href=${JSON.stringify(APP_HOME)};true;`)}>
          <Text style={styles.home}>Home</Text>
        </TouchableOpacity>
      </View>
      {loading && <View style={styles.loader}><ActivityIndicator size="large" color="#174ea6" /></View>}
      <WebView
        ref={browser}
        source={{ uri: APP_HOME }}
        originWhitelist={[APP_ORIGIN]}
        onShouldStartLoadWithRequest={({ url }) => isTrustedUrl(url)}
        onNavigationStateChange={({ canGoBack: value }) => setCanGoBack(value)}
        onLoadEnd={() => setLoading(false)}
        javaScriptEnabled
        domStorageEnabled
        sharedCookiesEnabled={false}
        thirdPartyCookiesEnabled={false}
        style={styles.web}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  header: { height: 54, paddingHorizontal: 16, backgroundColor: '#133b73', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  brand: { color: '#ffffff', fontSize: 18, fontWeight: '700' },
  home: { color: '#ffffff', fontSize: 14, fontWeight: '600' },
  loader: { position: 'absolute', top: 85, alignSelf: 'center', zIndex: 1 },
  web: { flex: 1 },
});
