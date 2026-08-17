package ai.tuesday.client;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class SetupActivity extends Activity {
    static final String PREFS = "tuesday_client";
    static final String PREF_BACKEND_URL = "backend_url";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(2, 8, 18));
        getWindow().setNavigationBarColor(Color.rgb(2, 8, 18));

        int pad = dp(24);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_VERTICAL);
        root.setPadding(pad, pad, pad, pad);
        root.setBackgroundColor(Color.rgb(2, 8, 18));

        TextView title = text(getString(R.string.setup_title), 22, Color.rgb(213, 248, 255));
        title.setLetterSpacing(0.12f);
        root.addView(title, matchWrap());

        TextView explanation = text(getString(R.string.setup_explanation), 14, Color.rgb(167, 195, 208));
        LinearLayout.LayoutParams explanationParams = matchWrap();
        explanationParams.setMargins(0, dp(12), 0, dp(18));
        root.addView(explanation, explanationParams);

        EditText url = new EditText(this);
        url.setHint(R.string.setup_hint);
        url.setSingleLine(true);
        url.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        url.setTextColor(Color.rgb(231, 246, 252));
        url.setHintTextColor(Color.rgb(118, 151, 168));
        url.setBackgroundColor(Color.rgb(6, 19, 33));
        url.setPadding(dp(12), dp(10), dp(12), dp(10));
        url.setText(getSharedPreferences(PREFS, MODE_PRIVATE).getString(PREF_BACKEND_URL, ""));
        root.addView(url, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(52)));

        TextView error = text("", 12, Color.rgb(255, 111, 135));
        LinearLayout.LayoutParams errorParams = matchWrap();
        errorParams.setMargins(0, dp(8), 0, dp(8));
        root.addView(error, errorParams);

        Button save = new Button(this);
        save.setText(R.string.save_and_open);
        save.setTextColor(Color.rgb(213, 248, 255));
        save.setBackgroundColor(Color.rgb(14, 48, 68));
        save.setOnClickListener(view -> {
            String normalized = UrlPolicy.normalizeBackend(url.getText().toString(), BuildConfig.DEBUG);
            if (normalized == null) {
                error.setText(R.string.invalid_url);
                return;
            }
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(PREF_BACKEND_URL, normalized).apply();
            setResult(RESULT_OK, new Intent().putExtra(PREF_BACKEND_URL, normalized));
            finish();
        });
        root.addView(save, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(52)));
        setContentView(root);
    }

    private TextView text(String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        return view;
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
