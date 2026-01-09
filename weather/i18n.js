/**
 * Internationalization (i18n) System for What About the Weather?
 * Lightweight translation support with auto-detection and manual switching.
 */

'use strict';

class I18n {
    constructor() {
        this.currentLang = 'en';
        this.fallbackLang = 'en';
        this.translations = {
            en: {
                // Navigation
                'nav.ephemeris': 'Ephemeris',
                'nav.geometry': 'Geometry',
                'nav.weather': 'Weather',
                'nav.triggers': 'Triggers',
                'nav.demo': 'Live Demo',

                // Hero
                'hero.badge': 'Technical Deep Dive',
                'hero.title': 'What About<br>the <em>Weather?</em>',
                'hero.subtitle': 'How astronomical calculations, window geometry, and weather data combine to create intelligent shade automation.',
                'hero.subtitle.emphasis': 'Because your home should know when to shield you from the sun — and when to let the storm roll in.',
                'hero.scroll': "Follow the sun's path",

                // Hero stats
                'stat.shades': 'Shades',
                'stat.orientations': 'Orientations',
                'stat.degrees': 'Degrees',
                'stat.interval': 'Min Interval',

                // Section titles
                'section.ephemeris.title': 'The <em>Ephemeris</em>',
                'section.ephemeris.description': "Where is the sun right now? Not from a weather API—calculated from orbital mechanics.",
                'section.ephemeris.whyCalculate': 'Why Calculate?',
                'section.ephemeris.whyCalculateDesc': "Weather APIs give you sunrise/sunset times—but that's not enough. We need the sun's <strong>exact position</strong> (azimuth and altitude) at any moment to know which windows have glare.",
                'section.geometry.title': 'Window <em>Geometry</em>',
                'section.geometry.description': 'A house with a view. 11 shades. 4 cardinal orientations. Which windows get sun when?',
                'section.geometry.intensityFunction': 'The Intensity Function',
                'section.geometry.intensityFunctionDesc': "Not all sun exposure is equal. We calculate <strong>glare intensity</strong> based on how directly the sun hits each window and the sun's altitude.",
                'section.geometry.directionConstants': 'Direction Constants',
                'section.weather.title': 'Weather <em>Integration</em>',
                'section.weather.description': 'Celestial calculations assume clear skies. Clouds change everything.',
                'section.weather.overrideLogic': 'The Override Logic',
                'section.weather.overrideLogicDesc': "When it's cloudy or raining, there's no glare to block. Weather data from OpenWeatherMap One Call API 3.0 can override celestial calculations.",
                'section.weather.conditions': 'Weather Conditions',
                'section.triggers.title': 'Celestial <em>Triggers</em>',
                'section.triggers.description': "Event-driven automation. The system doesn't poll—it watches for astronomical events.",
                'section.demo.title': 'Live <em>Demo</em>',
                'section.demo.description': 'Interactive simulation. Drag the time slider to see how shade recommendations change throughout the day.',
                'section.architecture.title': 'The <em>Architecture</em>',
                'section.architecture.description': "How it all fits together. From orbital mechanics to motor commands—this is where astronomy meets home comfort.",

                // Labels
                'label.azimuth': 'Azimuth',
                'label.altitude': 'Altitude',
                'label.direction': 'Direction',
                'label.isDay': 'Is Day',
                'label.weather': 'Weather',
                'label.cloudCoverage': 'Cloud Coverage',
                'label.timeOfDay': 'Time of Day',
                'label.includeWeather': 'Include Weather',
                'label.simulateClouds': 'Simulate clouds',
                'label.sunPosition': 'Sun Position',
                'label.shadeRecommendations': 'Shade Recommendations',

                // Timeline
                'timeline.sunrise': 'Sunrise',
                'timeline.sunrise.title': 'Morning Optimization',
                'timeline.sunrise.desc': 'East-facing windows get adjusted first. Living Room East (237) may close to 60% as morning sun streams in. Other shades stay open.',
                'timeline.noon': 'Solar Noon',
                'timeline.noon.title': 'Peak Sun',
                'timeline.noon.desc': 'South-facing windows see maximum exposure. Living South (235), Dining South (243), Entry (229) adjust based on altitude. High sun = less glare.',
                'timeline.afternoon': 'Afternoon',
                'timeline.afternoon.title': 'West Exposure',
                'timeline.afternoon.desc': 'Sun moves west. Primary West (68) and Bed 4 shades (359, 361) begin adjusting. Late afternoon sun is low and intense—maximum glare potential.',
                'timeline.dusk': 'Civil Dusk',
                'timeline.dusk.title': 'Evening Opening',
                'timeline.dusk.desc': 'Sun drops below horizon. All shades open to 100%. Enjoy the evening light. Prepare for sunset views.',

                // Weather conditions
                'weather.clear': 'Clear',
                'weather.mostly_clear': 'Mostly Clear',
                'weather.partly_cloudy': 'Partly Cloudy',
                'weather.overcast': 'Overcast',
                'weather.cloudy': 'Cloudy',
                'weather.fog': 'Fog',
                'weather.drizzle': 'Drizzle',
                'weather.rain': 'Rain',
                'weather.heavy_rain': 'Heavy Rain',
                'weather.showers': 'Showers',
                'weather.thunderstorm': 'Thunderstorm',
                'weather.snow': 'Snow',
                'weather.heavy_snow': 'Heavy Snow',

                // Table headers
                'table.shade': 'Shade',
                'table.room': 'Room',
                'table.facing': 'Facing',
                'table.glare': 'Glare',
                'table.level': 'Level',
                'table.reason': 'Reason',

                // Cards
                'card.azimuth.title': 'Azimuth',
                'card.azimuth.subtitle': '0° = North',
                'card.azimuth.body': "The sun's compass bearing. 0° is North, 90° is East, 180° is South, 270° is West. Tells us which direction the sun is shining.",
                'card.altitude.title': 'Altitude',
                'card.altitude.subtitle': '0° = Horizon',
                'card.altitude.body': "The sun's height above the horizon. 0° is sunrise/sunset, 90° is directly overhead. Lower sun = longer shadows = more glare through windows.",
                'card.isDay.title': 'Is Day',
                'card.isDay.subtitle': 'altitude > 0',
                'card.isDay.body': "Simple boolean—is the sun above the horizon? If not, we don't need to worry about glare. Open all shades for nighttime views.",

                // Callouts
                'callout.api.title': 'The Problem with APIs',
                'callout.api.content': "Weather APIs tell you <em>when</em> the sun rises. They don't tell you <em>where</em> it is at 2:47 PM or which direction it's shining. For that, I need to do the math myself. And honestly? It's beautiful math.",
                'callout.north.title': 'North-Facing = Always Open',
                'callout.north.content': "At Seattle's latitude (47.7°N), north-facing windows never get direct sun. So I leave those shades alone—let that soft, even light pour in.",
                'callout.seattle.title': 'Seattle Reality',
                'callout.seattle.content': "Seattle averages 226 cloudy days per year. So yes—the weather override isn't an edge case. It's the <em>common</em> case. But those 139 sunny days? They're worth getting right.",
                'callout.cbf.title': 'CBF Safety: I Respect Your Choices',
                'callout.cbf.content': "If you close a shade yourself, I won't fight you. The <code>ResidentOverrideCBF</code> (Control Barrier Function) protects your explicit intent for 30 minutes. Your judgment matters more than my algorithm.",

                // Footer
                'footer.subtitle': 'Where astronomy meets home comfort — built with care by Kagami',

                // Why Calculate
                'whyCalculate.title': 'Why Calculate?',
                'whyCalculate.content': "Weather APIs give you sunrise/sunset times—but that's not enough. We need the sun's <strong>exact position</strong> (azimuth and altitude) at any moment to know which windows have glare.",

                // Intensity Function
                'intensity.title': 'The Intensity Function',
                'intensity.content': 'Not all sun exposure is equal. We calculate <strong>glare intensity</strong> based on how directly the sun hits each window and the sun\'s altitude.',

                // Direction Constants
                'directions.title': 'Direction Constants',

                // Override Logic
                'override.title': 'The Override Logic',
                'override.content': "When it's cloudy or raining, there's no glare to block. Weather data from OpenWeatherMap One Call API 3.0 can override celestial calculations.",

                // Weather Conditions table
                'weather.conditions.title': 'Weather Conditions',

                // Architecture cards
                'arch.interval.title': 'Every 30 Minutes',
                'arch.interval.subtitle': 'Re-optimization interval',
                'arch.interval.body': "The sun moves ~7.5° every 30 minutes. That's enough to shift glare from one window orientation to another. Too frequent = motor wear. Too infrequent = stale recommendations.",
                'arch.cbf.title': 'CBF Protected',
                'arch.cbf.subtitle': 'Safety constraint',
                'arch.cbf.body': "Control Barrier Functions ensure <code>h(x) ≥ 0</code>. If you manually adjust a shade, the system won't override you. Your explicit intent is protected for 30 minutes.",
                'arch.portable.title': 'Portable',
                'arch.portable.subtitle': 'Location-agnostic',
                'arch.portable.body': "Home coordinates come from <code>config/location.yaml</code> or environment variables. Move houses? Just update the config. The algorithms don't change.",

                // Misc
                'yes': 'Yes',
                'no': 'No',
                'night': 'Night — open for views',
                'noSunOn': 'No sun on'
            },
            es: {
                // Navigation
                'nav.ephemeris': 'Efemérides',
                'nav.geometry': 'Geometría',
                'nav.weather': 'Clima',
                'nav.triggers': 'Disparadores',
                'nav.demo': 'Demo en Vivo',

                // Hero
                'hero.badge': 'Inmersión Técnica',
                'hero.title': '¿Y el <em>Clima?</em>',
                'hero.subtitle': 'Cómo los cálculos astronómicos, la geometría de ventanas y los datos climáticos se combinan para crear automatización inteligente de persianas.',
                'hero.subtitle.emphasis': 'Porque tu hogar debe saber cuándo protegerte del sol — y cuándo dejar entrar la tormenta.',
                'hero.scroll': 'Sigue el camino del sol',

                // Hero stats
                'stat.shades': 'Persianas',
                'stat.orientations': 'Orientaciones',
                'stat.degrees': 'Grados',
                'stat.interval': 'Intervalo Min',

                // Section titles
                'section.ephemeris.title': 'Las <em>Efemérides</em>',
                'section.ephemeris.desc': '¿Dónde está el sol ahora mismo? No desde una API meteorológica—calculado desde mecánica orbital.',
                'section.geometry.title': 'Geometría de <em>Ventanas</em>',
                'section.geometry.desc': 'Una casa con vista. 11 persianas. 4 orientaciones cardinales. ¿Qué ventanas reciben sol y cuándo?',
                'section.weather.title': 'Integración <em>Climática</em>',
                'section.weather.desc': 'Los cálculos celestes asumen cielos despejados. Las nubes lo cambian todo.',
                'section.triggers.title': 'Disparadores <em>Celestes</em>',
                'section.triggers.desc': 'Automatización basada en eventos. El sistema no consulta—observa eventos astronómicos.',
                'section.demo.title': 'Demo <em>en Vivo</em>',
                'section.demo.desc': 'Simulación interactiva. Arrastra el control de tiempo para ver cómo cambian las recomendaciones de persianas durante el día.',
                'section.architecture.title': 'La <em>Arquitectura</em>',
                'section.architecture.desc': 'Cómo todo encaja. Desde mecánica orbital hasta comandos de motor—aquí es donde la astronomía se encuentra con el confort del hogar.',

                // Labels
                'label.azimuth': 'Azimut',
                'label.altitude': 'Altitud',
                'label.direction': 'Dirección',
                'label.isDay': 'Es de Día',
                'label.weather': 'Clima',
                'label.cloudCoverage': 'Cobertura de Nubes',
                'label.timeOfDay': 'Hora del Día',
                'label.includeWeather': 'Incluir Clima',
                'label.simulateClouds': 'Simular nubes',
                'label.sunPosition': 'Posición del Sol',
                'label.shadeRecommendations': 'Recomendaciones de Persianas',

                // Timeline
                'timeline.sunrise': 'Amanecer',
                'timeline.sunrise.title': 'Optimización Matutina',
                'timeline.sunrise.desc': 'Las ventanas orientadas al este se ajustan primero. Living Room East (237) puede cerrar al 60% cuando entra el sol de la mañana.',
                'timeline.noon': 'Mediodía Solar',
                'timeline.noon.title': 'Sol Máximo',
                'timeline.noon.desc': 'Las ventanas orientadas al sur ven máxima exposición. Living South (235), Dining South (243), Entry (229) se ajustan según la altitud.',
                'timeline.afternoon': 'Tarde',
                'timeline.afternoon.title': 'Exposición Oeste',
                'timeline.afternoon.desc': 'El sol se mueve al oeste. Primary West (68) y las persianas de Bed 4 (359, 361) comienzan a ajustarse.',
                'timeline.dusk': 'Crepúsculo Civil',
                'timeline.dusk.title': 'Apertura Vespertina',
                'timeline.dusk.desc': 'El sol cae bajo el horizonte. Todas las persianas se abren al 100%. Disfruta de la luz del atardecer.',

                // Weather conditions
                'weather.clear': 'Despejado',
                'weather.mostly_clear': 'Mayormente Despejado',
                'weather.partly_cloudy': 'Parcialmente Nublado',
                'weather.overcast': 'Cubierto',
                'weather.cloudy': 'Nublado',
                'weather.fog': 'Niebla',
                'weather.drizzle': 'Llovizna',
                'weather.rain': 'Lluvia',
                'weather.heavy_rain': 'Lluvia Fuerte',
                'weather.showers': 'Chubascos',
                'weather.thunderstorm': 'Tormenta',
                'weather.snow': 'Nieve',
                'weather.heavy_snow': 'Nevada Fuerte',

                // Table headers
                'table.shade': 'Persiana',
                'table.room': 'Habitación',
                'table.facing': 'Orientación',
                'table.glare': 'Deslumbramiento',
                'table.level': 'Nivel',
                'table.reason': 'Razón',

                // Cards
                'card.azimuth.title': 'Azimut',
                'card.azimuth.subtitle': '0° = Norte',
                'card.azimuth.body': 'La orientación de brújula del sol. 0° es Norte, 90° es Este, 180° es Sur, 270° es Oeste. Indica la dirección del sol.',
                'card.altitude.title': 'Altitud',
                'card.altitude.subtitle': '0° = Horizonte',
                'card.altitude.body': 'La altura del sol sobre el horizonte. 0° es amanecer/atardecer, 90° es directamente arriba. Sol más bajo = sombras más largas = más deslumbramiento.',
                'card.isDay.title': 'Es de Día',
                'card.isDay.subtitle': 'altitud > 0',
                'card.isDay.body': 'Booleano simple—¿está el sol sobre el horizonte? Si no, no hay que preocuparse por el deslumbramiento. Abrir todas las persianas para vistas nocturnas.',

                // Callouts
                'callout.api.title': 'El Problema con las APIs',
                'callout.api.content': 'Las APIs meteorológicas te dicen <em>cuándo</em> sale el sol. No te dicen <em>dónde</em> está a las 2:47 PM o en qué dirección brilla. Para eso, necesito hacer las matemáticas yo mismo.',
                'callout.north.title': 'Norte = Siempre Abierto',
                'callout.north.content': 'En la latitud de Seattle (47.7°N), las ventanas orientadas al norte nunca reciben sol directo. Así que dejo esas persianas tranquilas—que entre esa luz suave y uniforme.',
                'callout.seattle.title': 'La Realidad de Seattle',
                'callout.seattle.content': 'Seattle promedia 226 días nublados al año. Así que sí—la anulación por clima no es un caso extremo. Es el caso <em>común</em>. Pero esos 139 días soleados? Vale la pena hacerlos bien.',
                'callout.cbf.title': 'Seguridad CBF: Respeto Tus Decisiones',
                'callout.cbf.content': 'Si cierras una persiana tú mismo, no voy a contradecirte. El <code>ResidentOverrideCBF</code> (Función de Barrera de Control) protege tu intención explícita por 30 minutos.',

                // Footer
                'footer.subtitle': 'Donde la astronomía se encuentra con el confort del hogar — construido con cuidado por Kagami',

                // Why Calculate
                'whyCalculate.title': '¿Por Qué Calcular?',
                'whyCalculate.content': 'Las APIs meteorológicas te dan horas de amanecer/atardecer—pero eso no es suficiente. Necesitamos la <strong>posición exacta</strong> del sol (azimut y altitud) en cualquier momento para saber qué ventanas tienen deslumbramiento.',

                // Intensity Function
                'intensity.title': 'La Función de Intensidad',
                'intensity.content': 'No toda la exposición solar es igual. Calculamos la <strong>intensidad del deslumbramiento</strong> basándonos en cuán directamente el sol golpea cada ventana y la altitud del sol.',

                // Direction Constants
                'directions.title': 'Constantes de Dirección',

                // Override Logic
                'override.title': 'La Lógica de Anulación',
                'override.content': 'Cuando está nublado o lloviendo, no hay deslumbramiento que bloquear. Los datos meteorológicos de OpenWeatherMap One Call API 3.0 pueden anular los cálculos celestes.',

                // Weather Conditions table
                'weather.conditions.title': 'Condiciones Climáticas',

                // Architecture cards
                'arch.interval.title': 'Cada 30 Minutos',
                'arch.interval.subtitle': 'Intervalo de re-optimización',
                'arch.interval.body': 'El sol se mueve ~7.5° cada 30 minutos. Eso es suficiente para cambiar el deslumbramiento de una orientación de ventana a otra.',
                'arch.cbf.title': 'Protegido por CBF',
                'arch.cbf.subtitle': 'Restricción de seguridad',
                'arch.cbf.body': 'Las Funciones de Barrera de Control aseguran <code>h(x) ≥ 0</code>. Si ajustas manualmente una persiana, el sistema no te anulará.',
                'arch.portable.title': 'Portátil',
                'arch.portable.subtitle': 'Agnóstico de ubicación',
                'arch.portable.body': 'Las coordenadas de la casa vienen de <code>config/location.yaml</code> o variables de entorno. ¿Te mudas? Solo actualiza la configuración.',

                // Misc
                'yes': 'Sí',
                'no': 'No',
                'night': 'Noche — abrir para vistas',
                'noSunOn': 'Sin sol en'
            },
            ja: {
                // Navigation
                'nav.ephemeris': '天体暦',
                'nav.geometry': '形状',
                'nav.weather': '天気',
                'nav.triggers': 'トリガー',
                'nav.demo': 'ライブデモ',

                // Hero
                'hero.badge': '技術的深掘り',
                'hero.title': '<em>天気</em>は<br>どうなの？',
                'hero.subtitle': '天文計算、窓の形状、気象データを組み合わせて、インテリジェントなシェード自動化を実現する方法。',
                'hero.subtitle.emphasis': '家は太陽から守るべき時と、嵐を迎え入れるべき時を知っているべきだから。',
                'hero.scroll': '太陽の軌跡をたどる',

                // Hero stats
                'stat.shades': 'シェード',
                'stat.orientations': '方位',
                'stat.degrees': '度',
                'stat.interval': '最小間隔',

                // Section titles
                'section.ephemeris.title': '<em>天体暦</em>',
                'section.ephemeris.desc': '太陽は今どこにある？天気APIからではなく—軌道力学から計算。',
                'section.geometry.title': '窓の<em>形状</em>',
                'section.geometry.desc': '眺めの良い家。11枚のシェード。4つの方位。どの窓がいつ日光を受ける？',
                'section.weather.title': '天気<em>統合</em>',
                'section.weather.desc': '天体計算は晴天を前提としている。雲がすべてを変える。',
                'section.triggers.title': '天体<em>トリガー</em>',
                'section.triggers.desc': 'イベント駆動の自動化。システムはポーリングしない—天文イベントを監視する。',
                'section.demo.title': 'ライブ<em>デモ</em>',
                'section.demo.desc': 'インタラクティブなシミュレーション。時間スライダーをドラッグして、一日を通してシェードの推奨がどう変化するか確認。',
                'section.architecture.title': '<em>アーキテクチャ</em>',
                'section.architecture.desc': 'すべてがどう組み合わさるか。軌道力学からモーターコマンドまで—天文学と家庭の快適さが出会う場所。',

                // Labels
                'label.azimuth': '方位角',
                'label.altitude': '高度',
                'label.direction': '方向',
                'label.isDay': '昼間か',
                'label.weather': '天気',
                'label.cloudCoverage': '雲量',
                'label.timeOfDay': '時刻',
                'label.includeWeather': '天気を含める',
                'label.simulateClouds': '雲をシミュレート',
                'label.sunPosition': '太陽の位置',
                'label.shadeRecommendations': 'シェード推奨',

                // Timeline
                'timeline.sunrise': '日の出',
                'timeline.sunrise.title': '朝の最適化',
                'timeline.sunrise.desc': '東向きの窓が最初に調整される。リビング東(237)は朝日が差し込むと60%まで閉じることがある。',
                'timeline.noon': '太陽の南中',
                'timeline.noon.title': 'ピーク時の太陽',
                'timeline.noon.desc': '南向きの窓は最大露出を受ける。リビング南(235)、ダイニング南(243)、エントリー(229)が高度に基づいて調整。',
                'timeline.afternoon': '午後',
                'timeline.afternoon.title': '西向き露出',
                'timeline.afternoon.desc': '太陽が西に移動。プライマリ西(68)とベッド4のシェード(359, 361)が調整を開始。',
                'timeline.dusk': '市民薄暮',
                'timeline.dusk.title': '夕方の開放',
                'timeline.dusk.desc': '太陽が地平線の下に沈む。すべてのシェードが100%開放。夕方の光を楽しむ。',

                // Weather conditions
                'weather.clear': '晴れ',
                'weather.mostly_clear': 'ほぼ晴れ',
                'weather.partly_cloudy': '時々曇り',
                'weather.overcast': '曇り',
                'weather.cloudy': '曇り',
                'weather.fog': '霧',
                'weather.drizzle': '霧雨',
                'weather.rain': '雨',
                'weather.heavy_rain': '大雨',
                'weather.showers': 'にわか雨',
                'weather.thunderstorm': '雷雨',
                'weather.snow': '雪',
                'weather.heavy_snow': '大雪',

                // Table headers
                'table.shade': 'シェード',
                'table.room': '部屋',
                'table.facing': '向き',
                'table.glare': 'まぶしさ',
                'table.level': 'レベル',
                'table.reason': '理由',

                // Cards
                'card.azimuth.title': '方位角',
                'card.azimuth.subtitle': '0° = 北',
                'card.azimuth.body': '太陽のコンパス方位。0°は北、90°は東、180°は南、270°は西。太陽がどの方向から照らしているかを示す。',
                'card.altitude.title': '高度',
                'card.altitude.subtitle': '0° = 地平線',
                'card.altitude.body': '地平線上の太陽の高さ。0°は日の出/日没、90°は真上。太陽が低い = 影が長い = まぶしさが増す。',
                'card.isDay.title': '昼間か',
                'card.isDay.subtitle': '高度 > 0',
                'card.isDay.body': 'シンプルなブール値—太陽は地平線の上にある？なければ、まぶしさを心配する必要はない。夜景のためにすべてのシェードを開ける。',

                // Callouts
                'callout.api.title': 'APIの問題点',
                'callout.api.content': '天気APIは太陽が<em>いつ</em>昇るか教えてくれる。午後2:47に<em>どこ</em>にあるか、どの方向に照らしているかは教えてくれない。それには自分で計算が必要。',
                'callout.north.title': '北向き = 常に開放',
                'callout.north.content': 'シアトルの緯度(47.7°N)では、北向きの窓は直射日光を受けない。だからそれらのシェードはそのまま—柔らかく均一な光を入れる。',
                'callout.seattle.title': 'シアトルの現実',
                'callout.seattle.content': 'シアトルは年間平均226日が曇り。そう—天気オーバーライドはエッジケースではない。<em>一般的な</em>ケースだ。',
                'callout.cbf.title': 'CBF安全性：あなたの選択を尊重',
                'callout.cbf.content': '自分でシェードを閉じたら、私は逆らわない。<code>ResidentOverrideCBF</code>があなたの明示的な意図を30分間保護する。',

                // Footer
                'footer.subtitle': '天文学と家庭の快適さが出会う場所 — Kagamiが心を込めて構築',

                // Why Calculate
                'whyCalculate.title': 'なぜ計算するのか？',
                'whyCalculate.content': '天気APIは日の出/日没時刻を提供する—でもそれだけでは足りない。どの窓がまぶしいか知るには、任意の瞬間の太陽の<strong>正確な位置</strong>（方位角と高度）が必要。',

                // Intensity Function
                'intensity.title': '強度関数',
                'intensity.content': 'すべての日光露出が等しいわけではない。太陽が各窓にどれだけ直接当たるかと太陽の高度に基づいて<strong>まぶしさの強度</strong>を計算する。',

                // Direction Constants
                'directions.title': '方向定数',

                // Override Logic
                'override.title': 'オーバーライドロジック',
                'override.content': '曇りや雨の時、遮るべきまぶしさはない。OpenWeatherMap One Call API 3.0の気象データが天体計算をオーバーライドできる。',

                // Weather Conditions table
                'weather.conditions.title': '天気条件',

                // Architecture cards
                'arch.interval.title': '30分ごと',
                'arch.interval.subtitle': '再最適化間隔',
                'arch.interval.body': '太陽は30分で約7.5°移動する。これは窓の向きによるまぶしさを変えるのに十分。',
                'arch.cbf.title': 'CBF保護',
                'arch.cbf.subtitle': '安全制約',
                'arch.cbf.body': '制御バリア関数が<code>h(x) ≥ 0</code>を保証する。手動でシェードを調整した場合、システムはオーバーライドしない。',
                'arch.portable.title': 'ポータブル',
                'arch.portable.subtitle': '場所に依存しない',
                'arch.portable.body': '家の座標は<code>config/location.yaml</code>または環境変数から取得。引っ越し？設定を更新するだけ。',

                // Misc
                'yes': 'はい',
                'no': 'いいえ',
                'night': '夜間 — 眺望のため開放',
                'noSunOn': '日光なし'
            },
            fr: {
                // Navigation
                'nav.ephemeris': 'Éphéméride',
                'nav.geometry': 'Géométrie',
                'nav.weather': 'Météo',
                'nav.triggers': 'Déclencheurs',
                'nav.demo': 'Démo en Direct',

                // Hero
                'hero.badge': 'Plongée Technique',
                'hero.title': 'Et la <em>Météo ?</em>',
                'hero.subtitle': "Comment les calculs astronomiques, la géométrie des fenêtres et les données météo se combinent pour créer une automatisation intelligente des stores.",
                'hero.subtitle.emphasis': 'Parce que votre maison devrait savoir quand vous protéger du soleil — et quand laisser entrer la tempête.',
                'hero.scroll': 'Suivez le chemin du soleil',

                // Hero stats
                'stat.shades': 'Stores',
                'stat.orientations': 'Orientations',
                'stat.degrees': 'Degrés',
                'stat.interval': 'Intervalle Min',

                // Section titles
                'section.ephemeris.title': "L'<em>Éphéméride</em>",
                'section.ephemeris.desc': "Où est le soleil en ce moment ? Pas depuis une API météo—calculé à partir de la mécanique orbitale.",
                'section.geometry.title': 'Géométrie des <em>Fenêtres</em>',
                'section.geometry.desc': 'Une maison avec vue. 11 stores. 4 orientations cardinales. Quelles fenêtres reçoivent le soleil et quand ?',
                'section.weather.title': 'Intégration <em>Météo</em>',
                'section.weather.desc': 'Les calculs célestes supposent un ciel dégagé. Les nuages changent tout.',
                'section.triggers.title': 'Déclencheurs <em>Célestes</em>',
                'section.triggers.desc': "Automatisation événementielle. Le système n'interroge pas—il surveille les événements astronomiques.",
                'section.demo.title': 'Démo <em>en Direct</em>',
                'section.demo.desc': 'Simulation interactive. Faites glisser le curseur de temps pour voir comment les recommandations de stores changent au cours de la journée.',
                'section.architecture.title': "L'<em>Architecture</em>",
                'section.architecture.desc': "Comment tout s'assemble. De la mécanique orbitale aux commandes moteur—là où l'astronomie rencontre le confort domestique.",

                // Labels
                'label.azimuth': 'Azimut',
                'label.altitude': 'Altitude',
                'label.direction': 'Direction',
                'label.isDay': 'Est-ce Jour',
                'label.weather': 'Météo',
                'label.cloudCoverage': 'Couverture Nuageuse',
                'label.timeOfDay': 'Heure du Jour',
                'label.includeWeather': 'Inclure la Météo',
                'label.simulateClouds': 'Simuler les nuages',
                'label.sunPosition': 'Position du Soleil',
                'label.shadeRecommendations': 'Recommandations de Stores',

                // Timeline
                'timeline.sunrise': 'Lever du Soleil',
                'timeline.sunrise.title': 'Optimisation Matinale',
                'timeline.sunrise.desc': "Les fenêtres orientées à l'est sont ajustées en premier. Living Room East (237) peut se fermer à 60% lorsque le soleil du matin entre.",
                'timeline.noon': 'Midi Solaire',
                'timeline.noon.title': 'Soleil Maximum',
                'timeline.noon.desc': "Les fenêtres orientées au sud voient une exposition maximale. Living South (235), Dining South (243), Entry (229) s'ajustent selon l'altitude.",
                'timeline.afternoon': 'Après-midi',
                'timeline.afternoon.title': "Exposition à l'Ouest",
                'timeline.afternoon.desc': "Le soleil se déplace vers l'ouest. Primary West (68) et les stores de Bed 4 (359, 361) commencent à s'ajuster.",
                'timeline.dusk': 'Crépuscule Civil',
                'timeline.dusk.title': 'Ouverture du Soir',
                'timeline.dusk.desc': "Le soleil passe sous l'horizon. Tous les stores s'ouvrent à 100%. Profitez de la lumière du soir.",

                // Weather conditions
                'weather.clear': 'Dégagé',
                'weather.mostly_clear': 'Principalement Dégagé',
                'weather.partly_cloudy': 'Partiellement Nuageux',
                'weather.overcast': 'Couvert',
                'weather.cloudy': 'Nuageux',
                'weather.fog': 'Brouillard',
                'weather.drizzle': 'Bruine',
                'weather.rain': 'Pluie',
                'weather.heavy_rain': 'Forte Pluie',
                'weather.showers': 'Averses',
                'weather.thunderstorm': 'Orage',
                'weather.snow': 'Neige',
                'weather.heavy_snow': 'Forte Neige',

                // Table headers
                'table.shade': 'Store',
                'table.room': 'Pièce',
                'table.facing': 'Orientation',
                'table.glare': 'Éblouissement',
                'table.level': 'Niveau',
                'table.reason': 'Raison',

                // Cards
                'card.azimuth.title': 'Azimut',
                'card.azimuth.subtitle': '0° = Nord',
                'card.azimuth.body': "Le cap de boussole du soleil. 0° est Nord, 90° est Est, 180° est Sud, 270° est Ouest.",
                'card.altitude.title': 'Altitude',
                'card.altitude.subtitle': "0° = Horizon",
                'card.altitude.body': "La hauteur du soleil au-dessus de l'horizon. 0° est lever/coucher, 90° est directement au-dessus.",
                'card.isDay.title': 'Est-ce Jour',
                'card.isDay.subtitle': 'altitude > 0',
                'card.isDay.body': "Simple booléen—le soleil est-il au-dessus de l'horizon ? Sinon, pas besoin de s'inquiéter de l'éblouissement.",

                // Callouts
                'callout.api.title': 'Le Problème avec les APIs',
                'callout.api.content': "Les APIs météo vous disent <em>quand</em> le soleil se lève. Elles ne vous disent pas <em>où</em> il est à 14h47.",
                'callout.north.title': 'Nord = Toujours Ouvert',
                'callout.north.content': "À la latitude de Seattle (47.7°N), les fenêtres orientées au nord ne reçoivent jamais de soleil direct.",
                'callout.seattle.title': 'La Réalité de Seattle',
                'callout.seattle.content': "Seattle compte en moyenne 226 jours nuageux par an. Le remplacement météo n'est pas un cas limite.",
                'callout.cbf.title': 'Sécurité CBF : Je Respecte Vos Choix',
                'callout.cbf.content': "Si vous fermez un store vous-même, je ne vous contredis pas. Le <code>ResidentOverrideCBF</code> protège votre intention explicite.",

                // Footer
                'footer.subtitle': "Où l'astronomie rencontre le confort domestique — construit avec soin par Kagami",

                // Why Calculate
                'whyCalculate.title': 'Pourquoi Calculer ?',
                'whyCalculate.content': "Les APIs météo vous donnent les heures de lever/coucher—mais ce n'est pas suffisant. Nous avons besoin de la <strong>position exacte</strong> du soleil à tout moment.",

                // Intensity Function
                'intensity.title': "La Fonction d'Intensité",
                'intensity.content': "Toute exposition au soleil n'est pas égale. Nous calculons <strong>l'intensité de l'éblouissement</strong> basée sur l'angle d'incidence.",

                // Direction Constants
                'directions.title': 'Constantes de Direction',

                // Override Logic
                'override.title': 'La Logique de Remplacement',
                'override.content': "Quand c'est nuageux ou pluvieux, il n'y a pas d'éblouissement à bloquer. Les données météo peuvent remplacer les calculs célestes.",

                // Weather Conditions table
                'weather.conditions.title': 'Conditions Météo',

                // Architecture cards
                'arch.interval.title': 'Toutes les 30 Minutes',
                'arch.interval.subtitle': 'Intervalle de ré-optimisation',
                'arch.interval.body': 'Le soleil se déplace de ~7.5° toutes les 30 minutes. Suffisant pour changer quel fenêtre est éblouie.',
                'arch.cbf.title': 'Protégé par CBF',
                'arch.cbf.subtitle': 'Contrainte de sécurité',
                'arch.cbf.body': "Les Fonctions de Barrière de Contrôle assurent <code>h(x) ≥ 0</code>. Le système ne vous contredira pas.",
                'arch.portable.title': 'Portable',
                'arch.portable.subtitle': 'Agnostique de lieu',
                'arch.portable.body': "Les coordonnées de la maison viennent de <code>config/location.yaml</code>. Vous déménagez ? Mettez à jour la config.",

                // Misc
                'yes': 'Oui',
                'no': 'Non',
                'night': 'Nuit — ouvert pour la vue',
                'noSunOn': 'Pas de soleil sur'
            }
        };

        this.detectLanguage();
    }

    /**
     * Detect browser language and set current language
     */
    detectLanguage() {
        const browserLang = navigator.language || navigator.userLanguage || 'en';
        const shortLang = browserLang.split('-')[0].toLowerCase();

        if (this.translations[shortLang]) {
            this.currentLang = shortLang;
        } else {
            this.currentLang = this.fallbackLang;
        }

        // Check for stored preference
        const storedLang = localStorage.getItem('preferredLanguage');
        if (storedLang && this.translations[storedLang]) {
            this.currentLang = storedLang;
        }

        return this.currentLang;
    }

    /**
     * Get translated string by key
     * @param {string} key - Translation key (e.g., 'nav.ephemeris')
     * @param {object} params - Optional parameters for interpolation
     * @returns {string} Translated string or key if not found
     */
    get(key, params = {}) {
        let translation = this.translations[this.currentLang]?.[key]
            || this.translations[this.fallbackLang]?.[key]
            || key;

        // Simple interpolation: replace {key} with params.key
        Object.keys(params).forEach(param => {
            translation = translation.replace(new RegExp(`{${param}}`, 'g'), params[param]);
        });

        return translation;
    }

    /**
     * Set current language
     * @param {string} lang - Language code (en, es, ja, fr)
     */
    setLang(lang) {
        if (!this.translations[lang]) {
            console.warn(`Language '${lang}' not supported. Available: ${this.getAvailableLangs().join(', ')}`);
            return false;
        }

        this.currentLang = lang;
        localStorage.setItem('preferredLanguage', lang);
        this.applyTranslations();

        // Update HTML lang attribute
        document.documentElement.lang = lang;

        // Dispatch event for other components
        window.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang } }));

        console.log(`%c Language set to: ${lang}`, 'color: #6366f1;');
        return true;
    }

    /**
     * Get current language code
     * @returns {string} Current language code
     */
    getCurrentLang() {
        return this.currentLang;
    }

    /**
     * Get list of available languages
     * @returns {string[]} Array of language codes
     */
    getAvailableLangs() {
        return Object.keys(this.translations);
    }

    /**
     * Apply translations to all elements with data-i18n attribute
     */
    applyTranslations() {
        // Translate elements with data-i18n attribute
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const translation = this.get(key);

            // Check if translation contains HTML
            if (translation.includes('<')) {
                el.innerHTML = translation;
            } else {
                el.textContent = translation;
            }
        });

        // Translate elements with data-i18n-placeholder attribute
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            el.placeholder = this.get(key);
        });

        // Translate elements with data-i18n-title attribute
        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            el.title = this.get(key);
        });

        // Translate elements with data-i18n-aria-label attribute
        document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
            const key = el.getAttribute('data-i18n-aria-label');
            el.setAttribute('aria-label', this.get(key));
        });

        // Update language selector active state
        document.querySelectorAll('.lang-option').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.lang === this.currentLang);
        });
    }

    /**
     * Create language selector UI
     * @returns {HTMLElement} Language selector element
     */
    createSelector() {
        const selector = document.createElement('div');
        selector.className = 'lang-selector';
        selector.setAttribute('role', 'group');
        selector.setAttribute('aria-label', 'Select language');

        const langs = [
            { code: 'en', label: 'EN', name: 'English' },
            { code: 'es', label: 'ES', name: 'Español' },
            { code: 'ja', label: 'JA', name: '日本語' },
            { code: 'fr', label: 'FR', name: 'Français' }
        ];

        langs.forEach(lang => {
            const btn = document.createElement('button');
            btn.className = `lang-option ${lang.code === this.currentLang ? 'active' : ''}`;
            btn.dataset.lang = lang.code;
            btn.setAttribute('title', lang.name);
            btn.setAttribute('aria-label', `Switch to ${lang.name}`);
            btn.textContent = lang.label;

            btn.addEventListener('click', () => {
                this.setLang(lang.code);
                // Play sound if available
                if (typeof sound !== 'undefined' && sound.enabled) {
                    sound.playClick();
                }
            });

            selector.appendChild(btn);
        });

        return selector;
    }

    /**
     * Initialize i18n - call after DOM is loaded
     */
    init() {
        // Set initial HTML lang attribute
        document.documentElement.lang = this.currentLang;

        // Apply initial translations
        this.applyTranslations();

        // Add language selector to nav
        const navLinks = document.querySelector('.nav-links');
        if (navLinks) {
            const selector = this.createSelector();
            navLinks.appendChild(selector);
        }
    }
}

// Create global i18n instance
const i18n = new I18n();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => i18n.init());
} else {
    i18n.init();
}
