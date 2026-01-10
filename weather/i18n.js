/**
 * Internationalization (i18n) System for What About the Weather?
 * Comprehensive translation support with 8 languages.
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
                'hero.title.line1': 'What About',
                'hero.title.line2': 'the <em>Weather?</em>',
                'hero.title': 'What About<br>the <em>Weather?</em>',
                'hero.subtitle': 'How astronomical calculations, window geometry, and weather data combine to create intelligent shade automation.',
                'hero.subtitle.emphasis': 'Because your home should know when to shield you from the sun — and when to let the storm roll in.',
                'hero.scroll': "Follow the sun's path",
                'hero.scrollAria': 'Scroll to learn more',

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

                // Demo labels
                'demo.timeOfDay': 'Time of Day',
                'demo.includeWeather': 'Include Weather',
                'demo.simulateClouds': 'Simulate clouds',
                'demo.sunPosition': 'Sun Position',
                'demo.shadeRecommendations': 'Shade Recommendations',

                // Timeline
                'timeline.sunrise.time': 'Sunrise',
                'timeline.sunrise.title': 'Morning Optimization',
                'timeline.sunrise.description': 'East-facing windows get adjusted first. Living Room East (237) may close to 60% as morning sun streams in. Other shades stay open.',
                'timeline.noon.time': 'Solar Noon',
                'timeline.noon.title': 'Peak Sun',
                'timeline.noon.description': 'South-facing windows see maximum exposure. Living South (235), Dining South (243), Entry (229) adjust based on altitude. High sun = less glare.',
                'timeline.afternoon.time': 'Afternoon',
                'timeline.afternoon.title': 'West Exposure',
                'timeline.afternoon.description': 'Sun moves west. Primary West (68) and Bed 4 shades (359, 361) begin adjusting. Late afternoon sun is low and intense—maximum glare potential.',
                'timeline.dusk.time': 'Civil Dusk',
                'timeline.dusk.title': 'Evening Opening',
                'timeline.dusk.description': 'Sun drops below horizon. All shades open to 100%. Enjoy the evening light. Prepare for sunset views.',

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
                'table.direction': 'Direction',
                'table.whatFacesIt': 'What Faces It',
                'table.sunTimes': 'Sun Times',
                'table.condition': 'Condition',
                'table.action': 'Action',
                'table.why': 'Why',

                // Cards - Ephemeris
                'card.azimuth.title': 'Azimuth',
                'card.azimuth.subtitle': '0° = North',
                'card.azimuth.body': "The sun's compass bearing. 0° is North, 90° is East, 180° is South, 270° is West. Tells us which direction the sun is shining.",
                'card.altitude.title': 'Altitude',
                'card.altitude.subtitle': '0° = Horizon',
                'card.altitude.body': "The sun's height above the horizon. 0° is sunrise/sunset, 90° is directly overhead. Lower sun = longer shadows = more glare through windows.",
                'card.isDay.title': 'Is Day',
                'card.isDay.subtitle': 'altitude > 0',
                'card.isDay.body': "Simple boolean—is the sun above the horizon? If not, we don't need to worry about glare. Open all shades for nighttime views.",

                // Cards - Architecture
                'card.interval.title': 'Every 30 Minutes',
                'card.interval.subtitle': 'Re-optimization interval',
                'card.interval.body': "The sun moves ~7.5° every 30 minutes. That's enough to shift glare from one window orientation to another. Too frequent = motor wear. Too infrequent = stale recommendations.",
                'card.cbfProtected.title': 'CBF Protected',
                'card.cbfProtected.subtitle': 'Safety constraint',
                'card.cbfProtected.body': "Control Barrier Functions ensure <code>h(x) ≥ 0</code>. If you manually adjust a shade, the system won't override you. Your explicit intent is protected for 30 minutes.",
                'card.portable.title': 'Portable',
                'card.portable.subtitle': 'Location-agnostic',
                'card.portable.body': "Home coordinates come from <code>config/location.yaml</code> or environment variables. Move houses? Just update the config. The algorithms don't change.",

                // Callouts
                'callout.problemApis.title': 'The Problem with APIs',
                'callout.problemApis.content': "Weather APIs tell you <em>when</em> the sun rises. They don't tell you <em>where</em> it is at 2:47 PM or which direction it's shining. For that, I need to do the math myself. And honestly? It's beautiful math.",
                'callout.northFacing.title': 'North-Facing = Always Open',
                'callout.northFacing.content': "At Seattle's latitude (47.7°N), north-facing windows never get direct sun. So I leave those shades alone—let that soft, even light pour in.",
                'callout.seattle.title': 'Seattle Reality',
                'callout.seattle.content': "Seattle averages 226 cloudy days per year. So yes—the weather override isn't an edge case. It's the <em>common</em> case. But those 139 sunny days? They're worth getting right.",
                'callout.cbf.title': 'CBF Safety: I Respect Your Choices',
                'callout.cbf.content': "If you close a shade yourself, I won't fight you. The <code>ResidentOverrideCBF</code> (Control Barrier Function) protects your explicit intent for 30 minutes. Your judgment matters more than my algorithm.",

                // Formula
                'formula.julian.title': 'Julian Date Calculation',
                'formula.julian.description': 'The foundation of all astronomical calculations. Converts calendar date to continuous day count since 4713 BCE.',

                // Diagram
                'diagram.dataFlow': 'Data Flow',

                // Footer
                'footer.title': 'What About the Weather?',
                'footer.subtitle': 'Where astronomy meets home comfort — built with care by Kagami',

                // Misc
                'yes': 'Yes',
                'no': 'No',
                'night': 'Night — open for views',
                'noSunOn': 'No sun on',
                
                // Compass & VR
                'compass.hint': 'Tap to enable device orientation',
                'compass.hint.enabled': 'Orientation enabled',
                'compass.orientationActive': 'Compass orientation active — dial is leveled',
                'secret.info.title': 'Secret Location',
                'secret.info.subtitle': 'Unlocked location details',
                'secret.info.revertTitle': 'Back to Your Location',
                'secret.info.revertSubtitle': 'Weather and globe reset to your coordinates',
                'secret.info.teleportHome': 'Welcome Home',
                'secret.info.teleportGeneric': 'Teleported to {location}',
                'secret.info.closeLabel': 'Close secret info',
                'weather.unknown': 'Unknown',
                'weather.sunrise': 'Sunrise',
                'weather.sunset': 'Sunset',
                'vr.enter': 'Enter VR',
                'vr.exit': 'Exit VR',
                'vr.enterAria': 'Enter immersive VR mode to view celestial bodies',
                'vr.exitAria': 'Exit immersive VR mode'
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
                'hero.title.line1': '¿Qué pasa con',
                'hero.title.line2': 'el <em>clima?</em>',
                'hero.title': '¿Y el <em>Clima?</em>',
                'hero.subtitle': 'Cómo los cálculos astronómicos, la geometría de ventanas y los datos climáticos se combinan para crear automatización inteligente de persianas.',
                'hero.subtitle.emphasis': 'Porque tu hogar debe saber cuándo protegerte del sol — y cuándo dejar entrar la tormenta.',
                'hero.scroll': 'Sigue el camino del sol',
                'hero.scrollAria': 'Desplázate para aprender más',

                // Hero stats
                'stat.shades': 'Persianas',
                'stat.orientations': 'Orientaciones',
                'stat.degrees': 'Grados',
                'stat.interval': 'Intervalo Min',

                // Section titles
                'section.ephemeris.title': 'Las <em>Efemérides</em>',
                'section.ephemeris.description': '¿Dónde está el sol ahora mismo? No desde una API meteorológica—calculado desde mecánica orbital.',
                'section.ephemeris.whyCalculate': '¿Por Qué Calcular?',
                'section.ephemeris.whyCalculateDesc': 'Las APIs meteorológicas te dan horas de amanecer/atardecer—pero eso no es suficiente. Necesitamos la <strong>posición exacta</strong> del sol (azimut y altitud) en cualquier momento.',
                'section.geometry.title': 'Geometría de <em>Ventanas</em>',
                'section.geometry.description': 'Una casa con vista. 11 persianas. 4 orientaciones cardinales. ¿Qué ventanas reciben sol y cuándo?',
                'section.geometry.intensityFunction': 'La Función de Intensidad',
                'section.geometry.intensityFunctionDesc': 'No toda la exposición solar es igual. Calculamos la <strong>intensidad del deslumbramiento</strong> basándonos en cuán directamente el sol golpea cada ventana.',
                'section.geometry.directionConstants': 'Constantes de Dirección',
                'section.weather.title': 'Integración <em>Climática</em>',
                'section.weather.description': 'Los cálculos celestes asumen cielos despejados. Las nubes lo cambian todo.',
                'section.weather.overrideLogic': 'La Lógica de Anulación',
                'section.weather.overrideLogicDesc': 'Cuando está nublado o lloviendo, no hay deslumbramiento que bloquear. Los datos meteorológicos pueden anular los cálculos celestes.',
                'section.weather.conditions': 'Condiciones Climáticas',
                'section.triggers.title': 'Disparadores <em>Celestes</em>',
                'section.triggers.description': 'Automatización basada en eventos. El sistema no consulta—observa eventos astronómicos.',
                'section.demo.title': 'Demo <em>en Vivo</em>',
                'section.demo.description': 'Simulación interactiva. Arrastra el control de tiempo para ver cómo cambian las recomendaciones durante el día.',
                'section.architecture.title': 'La <em>Arquitectura</em>',
                'section.architecture.description': 'Cómo todo encaja. Desde mecánica orbital hasta comandos de motor—donde la astronomía se encuentra con el confort.',

                // Labels
                'label.azimuth': 'Azimut',
                'label.altitude': 'Altitud',
                'label.direction': 'Dirección',
                'label.isDay': 'Es de Día',
                'label.weather': 'Clima',
                'label.cloudCoverage': 'Cobertura de Nubes',

                // Demo labels
                'demo.timeOfDay': 'Hora del Día',
                'demo.includeWeather': 'Incluir Clima',
                'demo.simulateClouds': 'Simular nubes',
                'demo.sunPosition': 'Posición del Sol',
                'demo.shadeRecommendations': 'Recomendaciones de Persianas',

                // Timeline
                'timeline.sunrise.time': 'Amanecer',
                'timeline.sunrise.title': 'Optimización Matutina',
                'timeline.sunrise.description': 'Las ventanas orientadas al este se ajustan primero. Living Room East (237) puede cerrar al 60% cuando entra el sol de la mañana.',
                'timeline.noon.time': 'Mediodía Solar',
                'timeline.noon.title': 'Sol Máximo',
                'timeline.noon.description': 'Las ventanas orientadas al sur ven máxima exposición. Living South (235), Dining South (243), Entry (229) se ajustan según la altitud.',
                'timeline.afternoon.time': 'Tarde',
                'timeline.afternoon.title': 'Exposición Oeste',
                'timeline.afternoon.description': 'El sol se mueve al oeste. Primary West (68) y las persianas de Bed 4 (359, 361) comienzan a ajustarse.',
                'timeline.dusk.time': 'Crepúsculo Civil',
                'timeline.dusk.title': 'Apertura Vespertina',
                'timeline.dusk.description': 'El sol cae bajo el horizonte. Todas las persianas se abren al 100%. Disfruta de la luz del atardecer.',

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
                'table.direction': 'Dirección',
                'table.whatFacesIt': 'Qué Da a',
                'table.sunTimes': 'Horas de Sol',
                'table.condition': 'Condición',
                'table.action': 'Acción',
                'table.why': 'Por Qué',

                // Cards - Ephemeris
                'card.azimuth.title': 'Azimut',
                'card.azimuth.subtitle': '0° = Norte',
                'card.azimuth.body': 'La orientación de brújula del sol. 0° es Norte, 90° es Este, 180° es Sur, 270° es Oeste.',
                'card.altitude.title': 'Altitud',
                'card.altitude.subtitle': '0° = Horizonte',
                'card.altitude.body': 'La altura del sol sobre el horizonte. 0° es amanecer/atardecer, 90° es directamente arriba.',
                'card.isDay.title': 'Es de Día',
                'card.isDay.subtitle': 'altitud > 0',
                'card.isDay.body': 'Booleano simple—¿está el sol sobre el horizonte? Si no, abrir todas las persianas para vistas nocturnas.',

                // Cards - Architecture
                'card.interval.title': 'Cada 30 Minutos',
                'card.interval.subtitle': 'Intervalo de re-optimización',
                'card.interval.body': 'El sol se mueve ~7.5° cada 30 minutos. Suficiente para cambiar el deslumbramiento de una ventana a otra.',
                'card.cbfProtected.title': 'Protegido por CBF',
                'card.cbfProtected.subtitle': 'Restricción de seguridad',
                'card.cbfProtected.body': 'Las Funciones de Barrera de Control aseguran <code>h(x) ≥ 0</code>. Si ajustas manualmente una persiana, el sistema no te anulará.',
                'card.portable.title': 'Portátil',
                'card.portable.subtitle': 'Agnóstico de ubicación',
                'card.portable.body': 'Las coordenadas de la casa vienen de <code>config/location.yaml</code>. ¿Te mudas? Solo actualiza la configuración.',

                // Callouts
                'callout.problemApis.title': 'El Problema con las APIs',
                'callout.problemApis.content': 'Las APIs meteorológicas te dicen <em>cuándo</em> sale el sol. No te dicen <em>dónde</em> está a las 2:47 PM o en qué dirección brilla.',
                'callout.northFacing.title': 'Norte = Siempre Abierto',
                'callout.northFacing.content': 'En la latitud de Seattle (47.7°N), las ventanas orientadas al norte nunca reciben sol directo.',
                'callout.seattle.title': 'La Realidad de Seattle',
                'callout.seattle.content': 'Seattle promedia 226 días nublados al año. El override por clima es el caso <em>común</em>.',
                'callout.cbf.title': 'Seguridad CBF',
                'callout.cbf.content': 'Si cierras una persiana tú mismo, no voy a contradecirte. El <code>ResidentOverrideCBF</code> protege tu intención.',

                // Formula
                'formula.julian.title': 'Cálculo de Fecha Juliana',
                'formula.julian.description': 'La base de todos los cálculos astronómicos. Convierte fecha calendario a conteo continuo de días.',

                // Diagram
                'diagram.dataFlow': 'Flujo de Datos',

                // Footer
                'footer.title': '¿Y el Clima?',
                'footer.subtitle': 'Donde la astronomía se encuentra con el confort del hogar — construido con cuidado por Kagami',

                // Misc
                'yes': 'Sí',
                'no': 'No',
                'night': 'Noche — abrir para vistas',
                'noSunOn': 'Sin sol en',
                
                // Compass & VR
                'compass.hint': 'Toca para activar la orientación del dispositivo',
                'compass.hint.enabled': 'Orientación habilitada',
                'compass.orientationActive': 'Orientación activa: la brújula está nivelada',
                'secret.info.title': 'Ubicación secreta',
                'secret.info.subtitle': 'Detalles desbloqueados',
                'secret.info.revertTitle': 'De vuelta a tu ubicación',
                'secret.info.revertSubtitle': 'Clima y globo reiniciados a tus coordenadas',
                'secret.info.teleportHome': 'Bienvenido a casa',
                'secret.info.teleportGeneric': 'Teletransportado a {location}',
                'secret.info.closeLabel': 'Cerrar información secreta',
                'weather.unknown': 'Desconocido',
                'weather.sunrise': 'Amanecer',
                'weather.sunset': 'Atardecer',
                'vr.enter': 'Entrar en VR',
                'vr.exit': 'Salir de VR',
                'vr.enterAria': 'Entrar en modo VR inmersivo para ver cuerpos celestes',
                'vr.exitAria': 'Salir del modo VR inmersivo'
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
                'hero.title.line1': '天気は',
                'hero.title.line2': '<em>どうなの？</em>',
                'hero.title': '<em>天気</em>は<br>どうなの？',
                'hero.subtitle': '天文計算、窓の形状、気象データを組み合わせて、インテリジェントなシェード自動化を実現。',
                'hero.subtitle.emphasis': '家は太陽から守るべき時と、嵐を迎え入れるべき時を知っているべき。',
                'hero.scroll': '太陽の軌跡をたどる',
                'hero.scrollAria': '詳しく見るにはスクロール',

                // Hero stats
                'stat.shades': 'シェード',
                'stat.orientations': '方位',
                'stat.degrees': '度',
                'stat.interval': '最小間隔',

                // Section titles
                'section.ephemeris.title': '<em>天体暦</em>',
                'section.ephemeris.description': '太陽は今どこにある？天気APIからではなく—軌道力学から計算。',
                'section.ephemeris.whyCalculate': 'なぜ計算するのか？',
                'section.ephemeris.whyCalculateDesc': '天気APIは日の出/日没時刻を提供する—でもそれだけでは足りない。<strong>正確な位置</strong>が必要。',
                'section.geometry.title': '窓の<em>形状</em>',
                'section.geometry.description': '眺めの良い家。11枚のシェード。4つの方位。どの窓がいつ日光を受ける？',
                'section.geometry.intensityFunction': '強度関数',
                'section.geometry.intensityFunctionDesc': 'すべての日光露出が等しいわけではない。<strong>まぶしさの強度</strong>を計算。',
                'section.geometry.directionConstants': '方向定数',
                'section.weather.title': '天気<em>統合</em>',
                'section.weather.description': '天体計算は晴天を前提としている。雲がすべてを変える。',
                'section.weather.overrideLogic': 'オーバーライドロジック',
                'section.weather.overrideLogicDesc': '曇りや雨の時、遮るべきまぶしさはない。気象データが天体計算をオーバーライドできる。',
                'section.weather.conditions': '天気条件',
                'section.triggers.title': '天体<em>トリガー</em>',
                'section.triggers.description': 'イベント駆動の自動化。システムはポーリングしない—天文イベントを監視。',
                'section.demo.title': 'ライブ<em>デモ</em>',
                'section.demo.description': 'インタラクティブなシミュレーション。時間スライダーをドラッグして変化を確認。',
                'section.architecture.title': '<em>アーキテクチャ</em>',
                'section.architecture.description': 'すべてがどう組み合わさるか。軌道力学からモーターコマンドまで。',

                // Labels
                'label.azimuth': '方位角',
                'label.altitude': '高度',
                'label.direction': '方向',
                'label.isDay': '昼間か',
                'label.weather': '天気',
                'label.cloudCoverage': '雲量',

                // Demo labels
                'demo.timeOfDay': '時刻',
                'demo.includeWeather': '天気を含める',
                'demo.simulateClouds': '雲をシミュレート',
                'demo.sunPosition': '太陽の位置',
                'demo.shadeRecommendations': 'シェード推奨',

                // Timeline
                'timeline.sunrise.time': '日の出',
                'timeline.sunrise.title': '朝の最適化',
                'timeline.sunrise.description': '東向きの窓が最初に調整される。リビング東(237)は朝日が差し込むと60%まで閉じることがある。',
                'timeline.noon.time': '太陽の南中',
                'timeline.noon.title': 'ピーク時の太陽',
                'timeline.noon.description': '南向きの窓は最大露出を受ける。高度に基づいて調整。',
                'timeline.afternoon.time': '午後',
                'timeline.afternoon.title': '西向き露出',
                'timeline.afternoon.description': '太陽が西に移動。プライマリ西(68)とベッド4のシェードが調整を開始。',
                'timeline.dusk.time': '市民薄暮',
                'timeline.dusk.title': '夕方の開放',
                'timeline.dusk.description': '太陽が地平線の下に沈む。すべてのシェードが100%開放。',

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
                'table.direction': '方向',
                'table.whatFacesIt': '面している部屋',
                'table.sunTimes': '日照時間',
                'table.condition': '条件',
                'table.action': 'アクション',
                'table.why': '理由',

                // Cards - Ephemeris
                'card.azimuth.title': '方位角',
                'card.azimuth.subtitle': '0° = 北',
                'card.azimuth.body': '太陽のコンパス方位。0°は北、90°は東、180°は南、270°は西。',
                'card.altitude.title': '高度',
                'card.altitude.subtitle': '0° = 地平線',
                'card.altitude.body': '地平線上の太陽の高さ。太陽が低い = 影が長い = まぶしさが増す。',
                'card.isDay.title': '昼間か',
                'card.isDay.subtitle': '高度 > 0',
                'card.isDay.body': '太陽は地平線の上にある？なければ、すべてのシェードを開ける。',

                // Cards - Architecture
                'card.interval.title': '30分ごと',
                'card.interval.subtitle': '再最適化間隔',
                'card.interval.body': '太陽は30分で約7.5°移動する。これは窓の向きによるまぶしさを変えるのに十分。',
                'card.cbfProtected.title': 'CBF保護',
                'card.cbfProtected.subtitle': '安全制約',
                'card.cbfProtected.body': '制御バリア関数が<code>h(x) ≥ 0</code>を保証する。手動で調整した場合、システムはオーバーライドしない。',
                'card.portable.title': 'ポータブル',
                'card.portable.subtitle': '場所に依存しない',
                'card.portable.body': '家の座標は<code>config/location.yaml</code>から取得。引っ越し？設定を更新するだけ。',

                // Callouts
                'callout.problemApis.title': 'APIの問題点',
                'callout.problemApis.content': '天気APIは太陽が<em>いつ</em>昇るか教えてくれる。<em>どこ</em>にあるかは教えてくれない。',
                'callout.northFacing.title': '北向き = 常に開放',
                'callout.northFacing.content': 'シアトルの緯度(47.7°N)では、北向きの窓は直射日光を受けない。',
                'callout.seattle.title': 'シアトルの現実',
                'callout.seattle.content': 'シアトルは年間平均226日が曇り。天気オーバーライドは<em>一般的な</em>ケース。',
                'callout.cbf.title': 'CBF安全性',
                'callout.cbf.content': '自分でシェードを閉じたら、私は逆らわない。<code>ResidentOverrideCBF</code>が意図を保護。',

                // Formula
                'formula.julian.title': 'ユリウス日計算',
                'formula.julian.description': 'すべての天文計算の基礎。カレンダー日付を紀元前4713年からの連続日数に変換。',

                // Diagram
                'diagram.dataFlow': 'データフロー',

                // Footer
                'footer.title': '天気はどうなの？',
                'footer.subtitle': '天文学と家庭の快適さが出会う場所 — Kagamiが心を込めて構築',

                // Misc
                'yes': 'はい',
                'no': 'いいえ',
                'night': '夜間 — 眺望のため開放',
                'noSunOn': '日光なし',
                
                // Compass & VR
                'compass.hint': 'タップして端末の向きを有効化',
                'compass.hint.enabled': '方位が有効になりました',
                'compass.orientationActive': 'コンパス補正が有効 — ダイヤルは水平です',
                'secret.info.title': 'シークレットロケーション',
                'secret.info.subtitle': '解放された場所の詳細',
                'secret.info.revertTitle': '元の場所に戻りました',
                'secret.info.revertSubtitle': '天気と地球儀をあなたの座標に同期',
                'secret.info.teleportHome': 'おかえりなさい',
                'secret.info.teleportGeneric': '{location} にテレポートしました',
                'secret.info.closeLabel': '秘密の情報を閉じる',
                'weather.unknown': '不明',
                'weather.sunrise': '日の出',
                'weather.sunset': '日の入り',
                'vr.enter': 'VRに入る',
                'vr.exit': 'VRを終了',
                'vr.enterAria': '天体を見る没入型VRモードに入る',
                'vr.exitAria': '没入型VRモードを終了する'
            },
            fr: {
                // Navigation
                'nav.ephemeris': 'Éphéméride',
                'nav.geometry': 'Géométrie',
                'nav.weather': 'Météo',
                'nav.triggers': 'Déclencheurs',
                'nav.demo': 'Démo',

                // Hero
                'hero.badge': 'Plongée Technique',
                'hero.title.line1': "Qu'en est-il",
                'hero.title.line2': 'de la <em>météo ?</em>',
                'hero.title': 'Et la <em>Météo ?</em>',
                'hero.subtitle': "Comment les calculs astronomiques, la géométrie des fenêtres et les données météo créent une automatisation intelligente.",
                'hero.subtitle.emphasis': 'Parce que votre maison devrait savoir quand vous protéger du soleil.',
                'hero.scroll': 'Suivez le chemin du soleil',
                'hero.scrollAria': 'Faites défiler pour en savoir plus',

                // Hero stats
                'stat.shades': 'Stores',
                'stat.orientations': 'Orientations',
                'stat.degrees': 'Degrés',
                'stat.interval': 'Intervalle Min',

                // Section titles
                'section.ephemeris.title': "L'<em>Éphéméride</em>",
                'section.ephemeris.description': "Où est le soleil ? Calculé à partir de la mécanique orbitale.",
                'section.ephemeris.whyCalculate': 'Pourquoi Calculer ?',
                'section.ephemeris.whyCalculateDesc': "Les APIs météo donnent les heures de lever/coucher—insuffisant. Nous avons besoin de la <strong>position exacte</strong>.",
                'section.geometry.title': 'Géométrie des <em>Fenêtres</em>',
                'section.geometry.description': 'Une maison avec vue. 11 stores. 4 orientations. Quelles fenêtres reçoivent le soleil ?',
                'section.geometry.intensityFunction': "Fonction d'Intensité",
                'section.geometry.intensityFunctionDesc': "Toute exposition n'est pas égale. Nous calculons <strong>l'intensité de l'éblouissement</strong>.",
                'section.geometry.directionConstants': 'Constantes de Direction',
                'section.weather.title': 'Intégration <em>Météo</em>',
                'section.weather.description': 'Les calculs célestes supposent un ciel dégagé. Les nuages changent tout.',
                'section.weather.overrideLogic': 'Logique de Remplacement',
                'section.weather.overrideLogicDesc': "Quand c'est nuageux, pas d'éblouissement à bloquer. Les données météo peuvent remplacer les calculs.",
                'section.weather.conditions': 'Conditions Météo',
                'section.triggers.title': 'Déclencheurs <em>Célestes</em>',
                'section.triggers.description': "Automatisation événementielle. Le système surveille les événements astronomiques.",
                'section.demo.title': 'Démo <em>en Direct</em>',
                'section.demo.description': 'Simulation interactive. Faites glisser le curseur pour voir les recommandations changer.',
                'section.architecture.title': "L'<em>Architecture</em>",
                'section.architecture.description': "Comment tout s'assemble. De la mécanique orbitale aux commandes moteur.",

                // Labels
                'label.azimuth': 'Azimut',
                'label.altitude': 'Altitude',
                'label.direction': 'Direction',
                'label.isDay': 'Est-ce Jour',
                'label.weather': 'Météo',
                'label.cloudCoverage': 'Couverture Nuageuse',

                // Demo labels
                'demo.timeOfDay': 'Heure du Jour',
                'demo.includeWeather': 'Inclure la Météo',
                'demo.simulateClouds': 'Simuler les nuages',
                'demo.sunPosition': 'Position du Soleil',
                'demo.shadeRecommendations': 'Recommandations de Stores',

                // Timeline
                'timeline.sunrise.time': 'Lever du Soleil',
                'timeline.sunrise.title': 'Optimisation Matinale',
                'timeline.sunrise.description': "Les fenêtres est sont ajustées en premier. Living Room East peut se fermer à 60%.",
                'timeline.noon.time': 'Midi Solaire',
                'timeline.noon.title': 'Soleil Maximum',
                'timeline.noon.description': "Les fenêtres sud voient une exposition maximale. Ajustement selon l'altitude.",
                'timeline.afternoon.time': 'Après-midi',
                'timeline.afternoon.title': "Exposition à l'Ouest",
                'timeline.afternoon.description': "Le soleil se déplace vers l'ouest. Les stores ouest s'ajustent.",
                'timeline.dusk.time': 'Crépuscule Civil',
                'timeline.dusk.title': 'Ouverture du Soir',
                'timeline.dusk.description': "Le soleil passe sous l'horizon. Tous les stores s'ouvrent à 100%.",

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
                'table.direction': 'Direction',
                'table.whatFacesIt': 'Ce qui y Fait Face',
                'table.sunTimes': 'Heures de Soleil',
                'table.condition': 'Condition',
                'table.action': 'Action',
                'table.why': 'Pourquoi',

                // Cards - Ephemeris
                'card.azimuth.title': 'Azimut',
                'card.azimuth.subtitle': '0° = Nord',
                'card.azimuth.body': "Le cap de boussole du soleil. 0° est Nord, 90° est Est, 180° est Sud.",
                'card.altitude.title': 'Altitude',
                'card.altitude.subtitle': "0° = Horizon",
                'card.altitude.body': "La hauteur du soleil au-dessus de l'horizon. Soleil bas = plus d'éblouissement.",
                'card.isDay.title': 'Est-ce Jour',
                'card.isDay.subtitle': 'altitude > 0',
                'card.isDay.body': "Le soleil est-il au-dessus de l'horizon ? Sinon, ouvrir tous les stores.",

                // Cards - Architecture
                'card.interval.title': 'Toutes les 30 Minutes',
                'card.interval.subtitle': 'Intervalle de ré-optimisation',
                'card.interval.body': 'Le soleil se déplace de ~7.5° toutes les 30 minutes. Suffisant pour changer le store à ajuster.',
                'card.cbfProtected.title': 'Protégé par CBF',
                'card.cbfProtected.subtitle': 'Contrainte de sécurité',
                'card.cbfProtected.body': "Les Fonctions de Barrière de Contrôle assurent <code>h(x) ≥ 0</code>. Le système ne vous contredira pas.",
                'card.portable.title': 'Portable',
                'card.portable.subtitle': 'Agnostique de lieu',
                'card.portable.body': "Les coordonnées viennent de <code>config/location.yaml</code>. Vous déménagez ? Mettez à jour la config.",

                // Callouts
                'callout.problemApis.title': 'Le Problème avec les APIs',
                'callout.problemApis.content': "Les APIs météo vous disent <em>quand</em> le soleil se lève. Pas <em>où</em> il est à 14h47.",
                'callout.northFacing.title': 'Nord = Toujours Ouvert',
                'callout.northFacing.content': "À la latitude de Seattle (47.7°N), les fenêtres nord ne reçoivent jamais de soleil direct.",
                'callout.seattle.title': 'La Réalité de Seattle',
                'callout.seattle.content': "Seattle compte 226 jours nuageux par an. Le remplacement météo est le cas <em>commun</em>.",
                'callout.cbf.title': 'Sécurité CBF',
                'callout.cbf.content': "Si vous fermez un store vous-même, je ne vous contredis pas. Le <code>ResidentOverrideCBF</code> protège votre intention.",

                // Formula
                'formula.julian.title': 'Calcul de Date Julienne',
                'formula.julian.description': 'La base de tous les calculs astronomiques. Convertit la date en jour continu.',

                // Diagram
                'diagram.dataFlow': 'Flux de Données',

                // Footer
                'footer.title': 'Et la Météo ?',
                'footer.subtitle': "Où l'astronomie rencontre le confort domestique — construit par Kagami",

                // Misc
                'yes': 'Oui',
                'no': 'Non',
                'night': 'Nuit — ouvert pour la vue',
                'noSunOn': 'Pas de soleil sur',
                
                // Compass & VR
                'compass.hint': "Touchez pour activer l’orientation de l’appareil",
                'compass.hint.enabled': 'Orientation activée',
                'compass.orientationActive': 'Orientation boussole active — le cadran est nivelé',
                'secret.info.title': 'Emplacement secret',
                'secret.info.subtitle': 'Détails débloqués',
                'secret.info.revertTitle': 'Retour à votre position',
                'secret.info.revertSubtitle': 'Météo et globe synchronisés sur vos coordonnées',
                'secret.info.teleportHome': 'Bienvenue chez vous',
                'secret.info.teleportGeneric': 'Téléporté à {location}',
                'secret.info.closeLabel': 'Fermer les infos secrètes',
                'weather.unknown': 'Inconnu',
                'weather.sunrise': 'Lever',
                'weather.sunset': 'Coucher',
                'vr.enter': 'Entrer en VR',
                'vr.exit': 'Quitter la VR',
                'vr.enterAria': "Entrer en mode VR immersif pour observer les corps célestes",
                'vr.exitAria': 'Quitter le mode VR immersif'
            },
            de: {
                // Navigation
                'nav.ephemeris': 'Ephemeride',
                'nav.geometry': 'Geometrie',
                'nav.weather': 'Wetter',
                'nav.triggers': 'Auslöser',
                'nav.demo': 'Live-Demo',

                // Hero
                'hero.badge': 'Technischer Tiefgang',
                'hero.title.line1': 'Was ist mit',
                'hero.title.line2': 'dem <em>Wetter?</em>',
                'hero.title': 'Was ist mit<br>dem <em>Wetter?</em>',
                'hero.subtitle': 'Wie astronomische Berechnungen, Fenstergeometrie und Wetterdaten intelligente Jalousienautomatisierung ermöglichen.',
                'hero.subtitle.emphasis': 'Weil Ihr Zuhause wissen sollte, wann es Sie vor der Sonne schützen muss.',
                'hero.scroll': 'Folge dem Sonnenpfad',
                'hero.scrollAria': 'Zum Entdecken nach unten scrollen',

                // Hero stats
                'stat.shades': 'Jalousien',
                'stat.orientations': 'Ausrichtungen',
                'stat.degrees': 'Grad',
                'stat.interval': 'Min Intervall',

                // Section titles
                'section.ephemeris.title': 'Die <em>Ephemeride</em>',
                'section.ephemeris.description': 'Wo ist die Sonne? Berechnet aus der Orbitalmechanik.',
                'section.ephemeris.whyCalculate': 'Warum Berechnen?',
                'section.ephemeris.whyCalculateDesc': 'Wetter-APIs liefern Sonnenauf-/untergangszeiten—aber das reicht nicht. Wir brauchen die <strong>genaue Position</strong>.',
                'section.geometry.title': 'Fenster<em>geometrie</em>',
                'section.geometry.description': 'Ein Haus mit Aussicht. 11 Jalousien. 4 Himmelsrichtungen. Welche Fenster bekommen wann Sonne?',
                'section.geometry.intensityFunction': 'Die Intensitätsfunktion',
                'section.geometry.intensityFunctionDesc': 'Nicht jede Sonneneinstrahlung ist gleich. Wir berechnen die <strong>Blendungsintensität</strong>.',
                'section.geometry.directionConstants': 'Richtungskonstanten',
                'section.weather.title': 'Wetter<em>integration</em>',
                'section.weather.description': 'Himmelsberechnungen setzen klaren Himmel voraus. Wolken ändern alles.',
                'section.weather.overrideLogic': 'Die Überschreibungslogik',
                'section.weather.overrideLogicDesc': 'Bei Bewölkung oder Regen gibt es keine Blendung zu blockieren.',
                'section.weather.conditions': 'Wetterbedingungen',
                'section.triggers.title': 'Himmlische <em>Auslöser</em>',
                'section.triggers.description': 'Ereignisgesteuerte Automatisierung. Das System überwacht astronomische Ereignisse.',
                'section.demo.title': 'Live-<em>Demo</em>',
                'section.demo.description': 'Interaktive Simulation. Ziehen Sie den Zeitregler, um zu sehen, wie sich Empfehlungen ändern.',
                'section.architecture.title': 'Die <em>Architektur</em>',
                'section.architecture.description': 'Wie alles zusammenpasst. Von Orbitalmechanik bis Motorbefehle.',

                // Labels
                'label.azimuth': 'Azimut',
                'label.altitude': 'Höhe',
                'label.direction': 'Richtung',
                'label.isDay': 'Ist Tag',
                'label.weather': 'Wetter',
                'label.cloudCoverage': 'Wolkendecke',

                // Demo labels
                'demo.timeOfDay': 'Tageszeit',
                'demo.includeWeather': 'Wetter einbeziehen',
                'demo.simulateClouds': 'Wolken simulieren',
                'demo.sunPosition': 'Sonnenposition',
                'demo.shadeRecommendations': 'Jalousienempfehlungen',

                // Timeline
                'timeline.sunrise.time': 'Sonnenaufgang',
                'timeline.sunrise.title': 'Morgenoptimierung',
                'timeline.sunrise.description': 'Ostfenster werden zuerst angepasst. Living Room East kann auf 60% schließen.',
                'timeline.noon.time': 'Sonnenhöchststand',
                'timeline.noon.title': 'Maximale Sonne',
                'timeline.noon.description': 'Südfenster sehen maximale Exposition. Anpassung basierend auf Höhe.',
                'timeline.afternoon.time': 'Nachmittag',
                'timeline.afternoon.title': 'Westexposition',
                'timeline.afternoon.description': 'Die Sonne wandert nach Westen. Westjalousien beginnen sich anzupassen.',
                'timeline.dusk.time': 'Bürgerliche Dämmerung',
                'timeline.dusk.title': 'Abendöffnung',
                'timeline.dusk.description': 'Die Sonne sinkt unter den Horizont. Alle Jalousien öffnen auf 100%.',

                // Weather conditions
                'weather.clear': 'Klar',
                'weather.mostly_clear': 'Meist Klar',
                'weather.partly_cloudy': 'Teilweise Bewölkt',
                'weather.overcast': 'Bedeckt',
                'weather.cloudy': 'Bewölkt',
                'weather.fog': 'Nebel',
                'weather.drizzle': 'Nieselregen',
                'weather.rain': 'Regen',
                'weather.heavy_rain': 'Starker Regen',
                'weather.showers': 'Schauer',
                'weather.thunderstorm': 'Gewitter',
                'weather.snow': 'Schnee',
                'weather.heavy_snow': 'Starker Schneefall',

                // Table headers
                'table.shade': 'Jalousie',
                'table.room': 'Raum',
                'table.facing': 'Ausrichtung',
                'table.glare': 'Blendung',
                'table.level': 'Stufe',
                'table.reason': 'Grund',
                'table.direction': 'Richtung',
                'table.whatFacesIt': 'Was es Zugewandt',
                'table.sunTimes': 'Sonnenzeiten',
                'table.condition': 'Bedingung',
                'table.action': 'Aktion',
                'table.why': 'Warum',

                // Cards - Ephemeris
                'card.azimuth.title': 'Azimut',
                'card.azimuth.subtitle': '0° = Nord',
                'card.azimuth.body': 'Die Kompassrichtung der Sonne. 0° ist Nord, 90° ist Ost, 180° ist Süd.',
                'card.altitude.title': 'Höhe',
                'card.altitude.subtitle': '0° = Horizont',
                'card.altitude.body': 'Die Höhe der Sonne über dem Horizont. Niedrigere Sonne = mehr Blendung.',
                'card.isDay.title': 'Ist Tag',
                'card.isDay.subtitle': 'Höhe > 0',
                'card.isDay.body': 'Ist die Sonne über dem Horizont? Falls nicht, alle Jalousien öffnen.',

                // Cards - Architecture
                'card.interval.title': 'Alle 30 Minuten',
                'card.interval.subtitle': 'Re-Optimierungsintervall',
                'card.interval.body': 'Die Sonne bewegt sich ~7,5° alle 30 Minuten. Genug, um die Blendung zu ändern.',
                'card.cbfProtected.title': 'CBF Geschützt',
                'card.cbfProtected.subtitle': 'Sicherheitsbeschränkung',
                'card.cbfProtected.body': 'Kontrollbarrierefunktionen stellen sicher <code>h(x) ≥ 0</code>. Das System überschreibt Sie nicht.',
                'card.portable.title': 'Portabel',
                'card.portable.subtitle': 'Ortsunabhängig',
                'card.portable.body': 'Hauskoordinaten kommen aus <code>config/location.yaml</code>. Umzug? Einfach aktualisieren.',

                // Callouts
                'callout.problemApis.title': 'Das Problem mit APIs',
                'callout.problemApis.content': 'Wetter-APIs sagen Ihnen <em>wann</em> die Sonne aufgeht. Nicht <em>wo</em> sie um 14:47 steht.',
                'callout.northFacing.title': 'Nord = Immer Offen',
                'callout.northFacing.content': 'Auf Seattles Breitengrad (47,7°N) bekommen Nordfenster nie direkte Sonne.',
                'callout.seattle.title': 'Seattle Realität',
                'callout.seattle.content': 'Seattle hat durchschnittlich 226 bewölkte Tage pro Jahr. Wetterüberschreibung ist der <em>Normalfall</em>.',
                'callout.cbf.title': 'CBF Sicherheit',
                'callout.cbf.content': 'Wenn Sie eine Jalousie selbst schließen, widerspreche ich nicht. <code>ResidentOverrideCBF</code> schützt Ihre Absicht.',

                // Formula
                'formula.julian.title': 'Julianisches Datum',
                'formula.julian.description': 'Die Grundlage aller astronomischen Berechnungen.',

                // Diagram
                'diagram.dataFlow': 'Datenfluss',

                // Footer
                'footer.title': 'Was ist mit dem Wetter?',
                'footer.subtitle': 'Wo Astronomie auf Wohnkomfort trifft — mit Sorgfalt gebaut von Kagami',

                // Misc
                'yes': 'Ja',
                'no': 'Nein',
                'night': 'Nacht — offen für die Aussicht',
                'noSunOn': 'Keine Sonne auf',
                
                // Compass & VR
                'compass.hint': 'Tippen, um die Geräteausrichtung zu aktivieren',
                'compass.hint.enabled': 'Ausrichtung aktiviert',
                'compass.orientationActive': 'Kompassausrichtung aktiv — Zifferblatt ist nivelliert',
                'secret.info.title': 'Geheimer Ort',
                'secret.info.subtitle': 'Freigeschaltete Details',
                'secret.info.revertTitle': 'Zurück an deinem Ort',
                'secret.info.revertSubtitle': 'Wetter und Globus auf deine Koordinaten gesetzt',
                'secret.info.teleportHome': 'Willkommen zu Hause',
                'secret.info.teleportGeneric': 'Nach {location} teleportiert',
                'secret.info.closeLabel': 'Geheime Infos schließen',
                'weather.unknown': 'Unbekannt',
                'weather.sunrise': 'Sonnenaufgang',
                'weather.sunset': 'Sonnenuntergang',
                'vr.enter': 'VR starten',
                'vr.exit': 'VR beenden',
                'vr.enterAria': 'In den immersiven VR-Modus wechseln, um Himmelskörper zu sehen',
                'vr.exitAria': 'Immersiven VR-Modus verlassen'
            },
            zh: {
                // Navigation
                'nav.ephemeris': '天文历',
                'nav.geometry': '几何',
                'nav.weather': '天气',
                'nav.triggers': '触发器',
                'nav.demo': '实时演示',

                // Hero
                'hero.badge': '技术深度',
                'hero.title.line1': '关于',
                'hero.title.line2': '<em>天气</em>怎么样？',
                'hero.title': '<em>天气</em><br>怎么样？',
                'hero.subtitle': '天文计算、窗户几何和天气数据如何结合创建智能窗帘自动化。',
                'hero.subtitle.emphasis': '因为您的家应该知道何时遮阳——何时让风暴进来。',
                'hero.scroll': '跟随太阳的轨迹',
                'hero.scrollAria': '向下滚动了解更多',

                // Hero stats
                'stat.shades': '窗帘',
                'stat.orientations': '朝向',
                'stat.degrees': '度',
                'stat.interval': '最小间隔',

                // Section titles
                'section.ephemeris.title': '<em>天文历</em>',
                'section.ephemeris.description': '太阳现在在哪里？不是从天气API获取——而是从轨道力学计算。',
                'section.ephemeris.whyCalculate': '为什么要计算？',
                'section.ephemeris.whyCalculateDesc': '天气API提供日出/日落时间——但这还不够。我们需要<strong>精确位置</strong>。',
                'section.geometry.title': '窗户<em>几何</em>',
                'section.geometry.description': '有景观的房子。11个窗帘。4个主要方向。哪些窗户何时有阳光？',
                'section.geometry.intensityFunction': '强度函数',
                'section.geometry.intensityFunctionDesc': '并非所有阳光照射都相同。我们计算<strong>眩光强度</strong>。',
                'section.geometry.directionConstants': '方向常数',
                'section.weather.title': '天气<em>集成</em>',
                'section.weather.description': '天体计算假设晴朗的天空。云彩改变一切。',
                'section.weather.overrideLogic': '覆盖逻辑',
                'section.weather.overrideLogicDesc': '多云或下雨时，没有眩光需要阻挡。天气数据可以覆盖天体计算。',
                'section.weather.conditions': '天气状况',
                'section.triggers.title': '天体<em>触发器</em>',
                'section.triggers.description': '事件驱动自动化。系统监视天文事件，不轮询。',
                'section.demo.title': '实时<em>演示</em>',
                'section.demo.description': '交互式模拟。拖动时间滑块查看建议如何变化。',
                'section.architecture.title': '<em>架构</em>',
                'section.architecture.description': '一切如何组合在一起。从轨道力学到电机命令。',

                // Labels
                'label.azimuth': '方位角',
                'label.altitude': '高度',
                'label.direction': '方向',
                'label.isDay': '是白天',
                'label.weather': '天气',
                'label.cloudCoverage': '云量',

                // Demo labels
                'demo.timeOfDay': '时间',
                'demo.includeWeather': '包含天气',
                'demo.simulateClouds': '模拟云',
                'demo.sunPosition': '太阳位置',
                'demo.shadeRecommendations': '窗帘建议',

                // Timeline
                'timeline.sunrise.time': '日出',
                'timeline.sunrise.title': '早晨优化',
                'timeline.sunrise.description': '朝东的窗户首先调整。Living Room East 可能关闭到60%。',
                'timeline.noon.time': '正午',
                'timeline.noon.title': '太阳最高点',
                'timeline.noon.description': '朝南的窗户接受最大曝光。根据高度调整。',
                'timeline.afternoon.time': '下午',
                'timeline.afternoon.title': '西面曝光',
                'timeline.afternoon.description': '太阳向西移动。西面窗帘开始调整。',
                'timeline.dusk.time': '民用黄昏',
                'timeline.dusk.title': '傍晚开放',
                'timeline.dusk.description': '太阳落到地平线以下。所有窗帘打开到100%。',

                // Weather conditions
                'weather.clear': '晴朗',
                'weather.mostly_clear': '大部分晴朗',
                'weather.partly_cloudy': '局部多云',
                'weather.overcast': '阴天',
                'weather.cloudy': '多云',
                'weather.fog': '雾',
                'weather.drizzle': '毛毛雨',
                'weather.rain': '雨',
                'weather.heavy_rain': '大雨',
                'weather.showers': '阵雨',
                'weather.thunderstorm': '雷暴',
                'weather.snow': '雪',
                'weather.heavy_snow': '大雪',

                // Table headers
                'table.shade': '窗帘',
                'table.room': '房间',
                'table.facing': '朝向',
                'table.glare': '眩光',
                'table.level': '级别',
                'table.reason': '原因',
                'table.direction': '方向',
                'table.whatFacesIt': '面对什么',
                'table.sunTimes': '日照时间',
                'table.condition': '条件',
                'table.action': '操作',
                'table.why': '原因',

                // Cards - Ephemeris
                'card.azimuth.title': '方位角',
                'card.azimuth.subtitle': '0° = 北',
                'card.azimuth.body': '太阳的罗盘方位。0°是北，90°是东，180°是南，270°是西。',
                'card.altitude.title': '高度',
                'card.altitude.subtitle': '0° = 地平线',
                'card.altitude.body': '太阳在地平线上的高度。太阳越低 = 影子越长 = 眩光越多。',
                'card.isDay.title': '是白天',
                'card.isDay.subtitle': '高度 > 0',
                'card.isDay.body': '太阳在地平线上吗？如果不是，打开所有窗帘欣赏夜景。',

                // Cards - Architecture
                'card.interval.title': '每30分钟',
                'card.interval.subtitle': '重新优化间隔',
                'card.interval.body': '太阳每30分钟移动约7.5°。足以改变哪个窗户受到眩光影响。',
                'card.cbfProtected.title': 'CBF保护',
                'card.cbfProtected.subtitle': '安全约束',
                'card.cbfProtected.body': '控制屏障函数确保<code>h(x) ≥ 0</code>。如果您手动调整，系统不会覆盖您。',
                'card.portable.title': '可移植',
                'card.portable.subtitle': '位置无关',
                'card.portable.body': '房屋坐标来自<code>config/location.yaml</code>。搬家？只需更新配置。',

                // Callouts
                'callout.problemApis.title': 'API的问题',
                'callout.problemApis.content': '天气API告诉您太阳<em>何时</em>升起。不告诉您下午2:47它在<em>哪里</em>。',
                'callout.northFacing.title': '北向 = 始终打开',
                'callout.northFacing.content': '在西雅图的纬度(47.7°N)，北向窗户从不接收直射阳光。',
                'callout.seattle.title': '西雅图现实',
                'callout.seattle.content': '西雅图平均每年226天多云。天气覆盖是<em>常见</em>情况。',
                'callout.cbf.title': 'CBF安全',
                'callout.cbf.content': '如果您自己关闭窗帘，我不会反对。<code>ResidentOverrideCBF</code>保护您的意图。',

                // Formula
                'formula.julian.title': '儒略日计算',
                'formula.julian.description': '所有天文计算的基础。将日历日期转换为连续天数。',

                // Diagram
                'diagram.dataFlow': '数据流',

                // Footer
                'footer.title': '天气怎么样？',
                'footer.subtitle': '天文学与家居舒适相遇——由Kagami用心打造',

                // Misc
                'yes': '是',
                'no': '否',
                'night': '夜间——打开欣赏景色',
                'noSunOn': '没有阳光在',
                
                // Compass & VR
                'compass.hint': '点按以启用设备方向',
                'compass.hint.enabled': '方向已启用',
                'compass.orientationActive': '罗盘校准已启用 — 表盘保持水平',
                'secret.info.title': '隐藏位置',
                'secret.info.subtitle': '已解锁的位置信息',
                'secret.info.revertTitle': '回到你的位置',
                'secret.info.revertSubtitle': '天气与地球同步到你的坐标',
                'secret.info.teleportHome': '欢迎回家',
                'secret.info.teleportGeneric': '已传送至 {location}',
                'secret.info.closeLabel': '关闭隐藏信息',
                'weather.unknown': '未知',
                'weather.sunrise': '日出',
                'weather.sunset': '日落',
                'vr.enter': '进入 VR',
                'vr.exit': '退出 VR',
                'vr.enterAria': '进入沉浸式VR模式以观察天体',
                'vr.exitAria': '退出沉浸式VR模式'
            },
            it: {
                // Navigation
                'nav.ephemeris': 'Effemeridi',
                'nav.geometry': 'Geometria',
                'nav.weather': 'Meteo',
                'nav.triggers': 'Trigger',
                'nav.demo': 'Demo Live',

                // Hero
                'hero.badge': 'Approfondimento Tecnico',
                'hero.title.line1': 'E il',
                'hero.title.line2': '<em>Meteo?</em>',
                'hero.title': 'E il <em>Meteo?</em>',
                'hero.subtitle': 'Come i calcoli astronomici, la geometria delle finestre e i dati meteo creano automazione intelligente delle tapparelle.',
                'hero.subtitle.emphasis': 'Perché la tua casa dovrebbe sapere quando proteggerti dal sole.',
                'hero.scroll': 'Segui il percorso del sole',
                'hero.scrollAria': 'Scorri per scoprire di più',

                // Hero stats
                'stat.shades': 'Tapparelle',
                'stat.orientations': 'Orientamenti',
                'stat.degrees': 'Gradi',
                'stat.interval': 'Intervallo Min',

                // Section titles
                'section.ephemeris.title': "Le <em>Effemeridi</em>",
                'section.ephemeris.description': "Dov'è il sole adesso? Calcolato dalla meccanica orbitale.",
                'section.ephemeris.whyCalculate': 'Perché Calcolare?',
                'section.ephemeris.whyCalculateDesc': "Le API meteo danno gli orari alba/tramonto—non basta. Serve la <strong>posizione esatta</strong>.",
                'section.geometry.title': 'Geometria delle <em>Finestre</em>',
                'section.geometry.description': 'Una casa con vista. 11 tapparelle. 4 orientamenti. Quali finestre ricevono sole e quando?',
                'section.geometry.intensityFunction': "Funzione d'Intensità",
                'section.geometry.intensityFunctionDesc': "Non tutta l'esposizione solare è uguale. Calcoliamo <strong>l'intensità dell'abbagliamento</strong>.",
                'section.geometry.directionConstants': 'Costanti di Direzione',
                'section.weather.title': 'Integrazione <em>Meteo</em>',
                'section.weather.description': 'I calcoli celesti assumono cieli sereni. Le nuvole cambiano tutto.',
                'section.weather.overrideLogic': 'Logica di Override',
                'section.weather.overrideLogicDesc': "Quando è nuvoloso, non c'è abbagliamento da bloccare. I dati meteo possono sovrascrivere i calcoli.",
                'section.weather.conditions': 'Condizioni Meteo',
                'section.triggers.title': 'Trigger <em>Celesti</em>',
                'section.triggers.description': 'Automazione basata su eventi. Il sistema monitora gli eventi astronomici.',
                'section.demo.title': 'Demo <em>Live</em>',
                'section.demo.description': 'Simulazione interattiva. Trascina il cursore del tempo per vedere come cambiano le raccomandazioni.',
                'section.architecture.title': "L'<em>Architettura</em>",
                'section.architecture.description': 'Come si incastra tutto. Dalla meccanica orbitale ai comandi motore.',

                // Labels
                'label.azimuth': 'Azimut',
                'label.altitude': 'Altitudine',
                'label.direction': 'Direzione',
                'label.isDay': 'È Giorno',
                'label.weather': 'Meteo',
                'label.cloudCoverage': 'Copertura Nuvolosa',

                // Demo labels
                'demo.timeOfDay': 'Ora del Giorno',
                'demo.includeWeather': 'Includi Meteo',
                'demo.simulateClouds': 'Simula nuvole',
                'demo.sunPosition': 'Posizione del Sole',
                'demo.shadeRecommendations': 'Raccomandazioni Tapparelle',

                // Timeline
                'timeline.sunrise.time': 'Alba',
                'timeline.sunrise.title': 'Ottimizzazione Mattutina',
                'timeline.sunrise.description': 'Le finestre est vengono regolate per prime. Living Room East può chiudersi al 60%.',
                'timeline.noon.time': 'Mezzogiorno Solare',
                'timeline.noon.title': 'Sole Massimo',
                'timeline.noon.description': "Le finestre sud vedono l'esposizione massima. Regolazione in base all'altitudine.",
                'timeline.afternoon.time': 'Pomeriggio',
                'timeline.afternoon.title': 'Esposizione Ovest',
                'timeline.afternoon.description': 'Il sole si sposta a ovest. Le tapparelle ovest iniziano a regolarsi.',
                'timeline.dusk.time': 'Crepuscolo Civile',
                'timeline.dusk.title': 'Apertura Serale',
                'timeline.dusk.description': "Il sole scende sotto l'orizzonte. Tutte le tapparelle si aprono al 100%.",

                // Weather conditions
                'weather.clear': 'Sereno',
                'weather.mostly_clear': 'Prevalentemente Sereno',
                'weather.partly_cloudy': 'Parzialmente Nuvoloso',
                'weather.overcast': 'Coperto',
                'weather.cloudy': 'Nuvoloso',
                'weather.fog': 'Nebbia',
                'weather.drizzle': 'Pioggerella',
                'weather.rain': 'Pioggia',
                'weather.heavy_rain': 'Pioggia Forte',
                'weather.showers': 'Rovesci',
                'weather.thunderstorm': 'Temporale',
                'weather.snow': 'Neve',
                'weather.heavy_snow': 'Forte Nevicata',

                // Table headers
                'table.shade': 'Tapparella',
                'table.room': 'Stanza',
                'table.facing': 'Orientamento',
                'table.glare': 'Abbagliamento',
                'table.level': 'Livello',
                'table.reason': 'Motivo',
                'table.direction': 'Direzione',
                'table.whatFacesIt': 'Cosa Guarda',
                'table.sunTimes': 'Orari Sole',
                'table.condition': 'Condizione',
                'table.action': 'Azione',
                'table.why': 'Perché',

                // Cards
                'card.azimuth.title': 'Azimut',
                'card.azimuth.subtitle': '0° = Nord',
                'card.azimuth.body': 'La direzione bussola del sole. 0° è Nord, 90° è Est, 180° è Sud.',
                'card.altitude.title': 'Altitudine',
                'card.altitude.subtitle': "0° = Orizzonte",
                'card.altitude.body': "L'altezza del sole sopra l'orizzonte. Sole basso = più abbagliamento.",
                'card.isDay.title': 'È Giorno',
                'card.isDay.subtitle': 'altitudine > 0',
                'card.isDay.body': "Il sole è sopra l'orizzonte? Altrimenti, aprire tutte le tapparelle.",
                'card.interval.title': 'Ogni 30 Minuti',
                'card.interval.subtitle': 'Intervallo di ri-ottimizzazione',
                'card.interval.body': 'Il sole si muove di ~7.5° ogni 30 minuti. Abbastanza per cambiare quale finestra è abbagliata.',
                'card.cbfProtected.title': 'Protetto da CBF',
                'card.cbfProtected.subtitle': 'Vincolo di sicurezza',
                'card.cbfProtected.body': 'Le Funzioni Barriera di Controllo assicurano <code>h(x) ≥ 0</code>. Il sistema non ti contraddirà.',
                'card.portable.title': 'Portatile',
                'card.portable.subtitle': 'Indipendente dalla posizione',
                'card.portable.body': 'Le coordinate della casa vengono da <code>config/location.yaml</code>. Ti trasferisci? Aggiorna la config.',

                // Callouts
                'callout.problemApis.title': 'Il Problema con le API',
                'callout.problemApis.content': "Le API meteo ti dicono <em>quando</em> sorge il sole. Non <em>dove</em> si trova alle 14:47.",
                'callout.northFacing.title': 'Nord = Sempre Aperto',
                'callout.northFacing.content': 'Alla latitudine di Seattle (47.7°N), le finestre nord non ricevono mai sole diretto.',
                'callout.seattle.title': 'La Realtà di Seattle',
                'callout.seattle.content': "Seattle ha in media 226 giorni nuvolosi all'anno. L'override meteo è il caso <em>comune</em>.",
                'callout.cbf.title': 'Sicurezza CBF',
                'callout.cbf.content': 'Se chiudi una tapparella tu stesso, non ti contraddico. <code>ResidentOverrideCBF</code> protegge la tua intenzione.',

                // Formula
                'formula.julian.title': 'Calcolo Data Giuliana',
                'formula.julian.description': 'La base di tutti i calcoli astronomici.',

                // Diagram
                'diagram.dataFlow': 'Flusso Dati',

                // Footer
                'footer.title': 'E il Meteo?',
                'footer.subtitle': "Dove l'astronomia incontra il comfort domestico — costruito con cura da Kagami",

                // Misc
                'yes': 'Sì',
                'no': 'No',
                'night': 'Notte — aperto per la vista',
                'noSunOn': 'Nessun sole su',
                
                // Compass & VR
                'compass.hint': 'Tocca per attivare l’orientamento del dispositivo',
                'compass.hint.enabled': 'Orientamento attivato',
                'compass.orientationActive': 'Orientamento bussola attivo — il quadrante è livellato',
                'secret.info.title': 'Posizione segreta',
                'secret.info.subtitle': 'Dettagli sbloccati',
                'secret.info.revertTitle': 'Tornato alla tua posizione',
                'secret.info.revertSubtitle': 'Meteo e globo sincronizzati alle tue coordinate',
                'secret.info.teleportHome': 'Bentornato a casa',
                'secret.info.teleportGeneric': 'Teletrasportato a {location}',
                'secret.info.closeLabel': 'Chiudi info segrete',
                'weather.unknown': 'Sconosciuto',
                'weather.sunrise': 'Alba',
                'weather.sunset': 'Tramonto',
                'vr.enter': 'Entra in VR',
                'vr.exit': 'Esci dalla VR',
                'vr.enterAria': 'Entra in VR immersiva per osservare i corpi celesti',
                'vr.exitAria': 'Esci dalla modalità VR immersiva'
            },
            pt: {
                // Navigation
                'nav.ephemeris': 'Efemérides',
                'nav.geometry': 'Geometria',
                'nav.weather': 'Clima',
                'nav.triggers': 'Gatilhos',
                'nav.demo': 'Demo ao Vivo',

                // Hero
                'hero.badge': 'Aprofundamento Técnico',
                'hero.title.line1': 'E o',
                'hero.title.line2': '<em>Clima?</em>',
                'hero.title': 'E o <em>Clima?</em>',
                'hero.subtitle': 'Como cálculos astronômicos, geometria de janelas e dados climáticos criam automação inteligente de persianas.',
                'hero.subtitle.emphasis': 'Porque sua casa deve saber quando te proteger do sol.',
                'hero.scroll': 'Siga o caminho do sol',
                'hero.scrollAria': 'Role para saber mais',

                // Hero stats
                'stat.shades': 'Persianas',
                'stat.orientations': 'Orientações',
                'stat.degrees': 'Graus',
                'stat.interval': 'Intervalo Min',

                // Section titles
                'section.ephemeris.title': 'As <em>Efemérides</em>',
                'section.ephemeris.description': 'Onde está o sol agora? Calculado da mecânica orbital.',
                'section.ephemeris.whyCalculate': 'Por Que Calcular?',
                'section.ephemeris.whyCalculateDesc': 'APIs de clima dão horários de nascer/pôr do sol—mas não basta. Precisamos da <strong>posição exata</strong>.',
                'section.geometry.title': 'Geometria das <em>Janelas</em>',
                'section.geometry.description': 'Uma casa com vista. 11 persianas. 4 orientações. Quais janelas recebem sol e quando?',
                'section.geometry.intensityFunction': 'Função de Intensidade',
                'section.geometry.intensityFunctionDesc': 'Nem toda exposição solar é igual. Calculamos a <strong>intensidade do ofuscamento</strong>.',
                'section.geometry.directionConstants': 'Constantes de Direção',
                'section.weather.title': 'Integração <em>Climática</em>',
                'section.weather.description': 'Cálculos celestes assumem céus claros. Nuvens mudam tudo.',
                'section.weather.overrideLogic': 'Lógica de Substituição',
                'section.weather.overrideLogicDesc': 'Quando está nublado, não há ofuscamento para bloquear. Dados climáticos podem substituir os cálculos.',
                'section.weather.conditions': 'Condições Climáticas',
                'section.triggers.title': 'Gatilhos <em>Celestes</em>',
                'section.triggers.description': 'Automação baseada em eventos. O sistema monitora eventos astronômicos.',
                'section.demo.title': 'Demo <em>ao Vivo</em>',
                'section.demo.description': 'Simulação interativa. Arraste o controle de tempo para ver as recomendações mudarem.',
                'section.architecture.title': 'A <em>Arquitetura</em>',
                'section.architecture.description': 'Como tudo se encaixa. Da mecânica orbital aos comandos de motor.',

                // Labels
                'label.azimuth': 'Azimute',
                'label.altitude': 'Altitude',
                'label.direction': 'Direção',
                'label.isDay': 'É Dia',
                'label.weather': 'Clima',
                'label.cloudCoverage': 'Cobertura de Nuvens',

                // Demo labels
                'demo.timeOfDay': 'Hora do Dia',
                'demo.includeWeather': 'Incluir Clima',
                'demo.simulateClouds': 'Simular nuvens',
                'demo.sunPosition': 'Posição do Sol',
                'demo.shadeRecommendations': 'Recomendações de Persianas',

                // Timeline
                'timeline.sunrise.time': 'Nascer do Sol',
                'timeline.sunrise.title': 'Otimização Matinal',
                'timeline.sunrise.description': 'Janelas leste são ajustadas primeiro. Living Room East pode fechar para 60%.',
                'timeline.noon.time': 'Meio-dia Solar',
                'timeline.noon.title': 'Sol Máximo',
                'timeline.noon.description': 'Janelas sul veem exposição máxima. Ajuste baseado na altitude.',
                'timeline.afternoon.time': 'Tarde',
                'timeline.afternoon.title': 'Exposição Oeste',
                'timeline.afternoon.description': 'O sol se move para oeste. Persianas oeste começam a ajustar.',
                'timeline.dusk.time': 'Crepúsculo Civil',
                'timeline.dusk.title': 'Abertura Noturna',
                'timeline.dusk.description': 'O sol desce abaixo do horizonte. Todas as persianas abrem para 100%.',

                // Weather conditions
                'weather.clear': 'Limpo',
                'weather.mostly_clear': 'Maiormente Limpo',
                'weather.partly_cloudy': 'Parcialmente Nublado',
                'weather.overcast': 'Encoberto',
                'weather.cloudy': 'Nublado',
                'weather.fog': 'Neblina',
                'weather.drizzle': 'Garoa',
                'weather.rain': 'Chuva',
                'weather.heavy_rain': 'Chuva Forte',
                'weather.showers': 'Pancadas',
                'weather.thunderstorm': 'Tempestade',
                'weather.snow': 'Neve',
                'weather.heavy_snow': 'Neve Forte',

                // Table headers
                'table.shade': 'Persiana',
                'table.room': 'Sala',
                'table.facing': 'Orientação',
                'table.glare': 'Ofuscamento',
                'table.level': 'Nível',
                'table.reason': 'Motivo',
                'table.direction': 'Direção',
                'table.whatFacesIt': 'O Que Enfrenta',
                'table.sunTimes': 'Horários de Sol',
                'table.condition': 'Condição',
                'table.action': 'Ação',
                'table.why': 'Por Que',

                // Cards
                'card.azimuth.title': 'Azimute',
                'card.azimuth.subtitle': '0° = Norte',
                'card.azimuth.body': 'A direção da bússola do sol. 0° é Norte, 90° é Leste, 180° é Sul.',
                'card.altitude.title': 'Altitude',
                'card.altitude.subtitle': '0° = Horizonte',
                'card.altitude.body': 'A altura do sol acima do horizonte. Sol baixo = mais ofuscamento.',
                'card.isDay.title': 'É Dia',
                'card.isDay.subtitle': 'altitude > 0',
                'card.isDay.body': 'O sol está acima do horizonte? Senão, abrir todas as persianas.',
                'card.interval.title': 'A Cada 30 Minutos',
                'card.interval.subtitle': 'Intervalo de re-otimização',
                'card.interval.body': 'O sol se move ~7.5° a cada 30 minutos. Suficiente para mudar qual janela está ofuscada.',
                'card.cbfProtected.title': 'Protegido por CBF',
                'card.cbfProtected.subtitle': 'Restrição de segurança',
                'card.cbfProtected.body': 'Funções de Barreira de Controle garantem <code>h(x) ≥ 0</code>. O sistema não vai contradizê-lo.',
                'card.portable.title': 'Portátil',
                'card.portable.subtitle': 'Independente de localização',
                'card.portable.body': 'Coordenadas da casa vêm de <code>config/location.yaml</code>. Mudou? Atualize a config.',

                // Callouts
                'callout.problemApis.title': 'O Problema com APIs',
                'callout.problemApis.content': 'APIs de clima dizem <em>quando</em> o sol nasce. Não <em>onde</em> ele está às 14:47.',
                'callout.northFacing.title': 'Norte = Sempre Aberto',
                'callout.northFacing.content': 'Na latitude de Seattle (47.7°N), janelas norte nunca recebem sol direto.',
                'callout.seattle.title': 'Realidade de Seattle',
                'callout.seattle.content': 'Seattle tem média de 226 dias nublados por ano. Substituição por clima é o caso <em>comum</em>.',
                'callout.cbf.title': 'Segurança CBF',
                'callout.cbf.content': 'Se você fechar uma persiana, não vou contradizê-lo. <code>ResidentOverrideCBF</code> protege sua intenção.',

                // Formula
                'formula.julian.title': 'Cálculo de Data Juliana',
                'formula.julian.description': 'A base de todos os cálculos astronômicos.',

                // Diagram
                'diagram.dataFlow': 'Fluxo de Dados',

                // Footer
                'footer.title': 'E o Clima?',
                'footer.subtitle': 'Onde astronomia encontra conforto doméstico — construído com cuidado por Kagami',

                // Misc
                'yes': 'Sim',
                'no': 'Não',
                'night': 'Noite — aberto para a vista',
                'noSunOn': 'Sem sol em',
                
                // Compass & VR
                'compass.hint': 'Toque para ativar a orientação do dispositivo',
                'compass.hint.enabled': 'Orientação ativada',
                'compass.orientationActive': 'Orientação da bússola ativa — o mostrador está nivelado',
                'secret.info.title': 'Local secreto',
                'secret.info.subtitle': 'Detalhes desbloqueados',
                'secret.info.revertTitle': 'De volta à sua localização',
                'secret.info.revertSubtitle': 'Clima e globo sincronizados às suas coordenadas',
                'secret.info.teleportHome': 'Bem-vindo de volta',
                'secret.info.teleportGeneric': 'Teletransportado para {location}',
                'secret.info.closeLabel': 'Fechar info secreta',
                'weather.unknown': 'Desconhecido',
                'weather.sunrise': 'Nascer do sol',
                'weather.sunset': 'Pôr do sol',
                'vr.enter': 'Entrar em VR',
                'vr.exit': 'Sair da VR',
                'vr.enterAria': 'Entrar no modo VR imersivo para ver corpos celestes',
                'vr.exitAria': 'Sair do modo VR imersivo'
            },

            // Arabic (RTL)
            ar: {
                'nav.ephemeris': 'التقويم الفلكي',
                'nav.geometry': 'الهندسة',
                'nav.weather': 'الطقس',
                'nav.triggers': 'المحفزات',
                'nav.demo': 'عرض مباشر',
                'hero.badge': 'دراسة تقنية معمقة',
                'hero.title.line1': 'ماذا عن',
                'hero.title.line2': '<em>الطقس؟</em>',
                'hero.title': 'ماذا عن <em>الطقس؟</em>',
                'hero.subtitle': 'كيف تجتمع الحسابات الفلكية وهندسة النوافذ وبيانات الطقس لإنشاء أتمتة ذكية للستائر.',
                'hero.scroll': 'تتبع مسار الشمس',
                'hero.scrollAria': 'مرر لأسفل للتعرف أكثر',
                'stat.shades': 'الستائر',
                'stat.orientations': 'الاتجاهات',
                'stat.degrees': 'الدرجات',
                'stat.interval': 'الفاصل',
                'section.ephemeris.title': '<em>التقويم</em> الفلكي',
                'section.ephemeris.description': 'أين الشمس الآن؟ محسوبة من ميكانيكا المدارات.',
                'section.geometry.title': 'هندسة <em>النوافذ</em>',
                'section.geometry.description': 'منزل بإطلالة. ١١ ستارة. ٤ اتجاهات.',
                'section.weather.title': 'تكامل <em>الطقس</em>',
                'section.weather.description': 'الحسابات الفلكية تفترض سماء صافية. الغيوم تغير كل شيء.',
                'section.triggers.title': 'المحفزات <em>الفلكية</em>',
                'section.triggers.description': 'أتمتة قائمة على الأحداث.',
                'section.demo.title': 'عرض <em>مباشر</em>',
                'section.demo.description': 'محاكاة تفاعلية. اسحب منزلق الوقت.',
                'section.architecture.title': '<em>البنية</em>',
                'section.architecture.description': 'كيف يتكامل كل شيء.',
                'label.azimuth': 'السمت',
                'label.altitude': 'الارتفاع',
                'label.direction': 'الاتجاه',
                'label.isDay': 'نهار',
                'label.weather': 'الطقس',
                'label.cloudCoverage': 'تغطية الغيوم',
                'demo.timeOfDay': 'وقت اليوم',
                'demo.includeWeather': 'تضمين الطقس',
                'demo.sunPosition': 'موقع الشمس',
                'demo.shadeRecommendations': 'توصيات الستائر',
                'footer.title': 'ماذا عن الطقس؟',
                'footer.subtitle': 'حيث يلتقي علم الفلك براحة المنزل',
                'yes': 'نعم',
                'no': 'لا',
                
                // Compass & VR
                'compass.hint': 'اضغط لتفعيل اتجاه الجهاز',
                'compass.hint.enabled': 'تم تفعيل الاتجاه',
                'compass.orientationActive': 'البوصلة مفعلة — القرص مستوٍ',
                'secret.info.title': 'موقع سري',
                'secret.info.subtitle': 'تفاصيل تم فتحها',
                'secret.info.revertTitle': 'الرجوع إلى موقعك',
                'secret.info.revertSubtitle': 'تمت مزامنة الطقس والكرة مع إحداثياتك',
                'secret.info.teleportHome': 'مرحباً بعودتك',
                'secret.info.teleportGeneric': 'تم النقل إلى {location}',
                'secret.info.closeLabel': 'إغلاق المعلومات السرية',
                'weather.unknown': 'غير معروف',
                'weather.sunrise': 'شروق الشمس',
                'weather.sunset': 'غروب الشمس',
                'vr.enter': 'دخول الواقع الافتراضي',
                'vr.exit': 'الخروج من الواقع الافتراضي',
                'vr.enterAria': 'دخول وضع الواقع الافتراضي لمشاهدة الأجرام السماوية',
                'vr.exitAria': 'الخروج من وضع الواقع الافتراضي'
            },

            // Hebrew (RTL)
            he: {
                'nav.ephemeris': 'אפמריס',
                'nav.geometry': 'גאומטריה',
                'nav.weather': 'מזג אוויר',
                'nav.triggers': 'טריגרים',
                'nav.demo': 'הדגמה חיה',
                'hero.badge': 'צלילה טכנית מעמיקה',
                'hero.title.line1': 'מה עם',
                'hero.title.line2': '<em>מזג האוויר?</em>',
                'hero.title': 'מה עם <em>מזג האוויר?</em>',
                'hero.subtitle': 'כיצד חישובים אסטרונומיים וגאומטריית חלונות יוצרים אוטומציה חכמה.',
                'hero.scroll': 'עקוב אחר נתיב השמש',
                'hero.scrollAria': 'גלול למטה כדי ללמוד עוד',
                'stat.shades': 'תריסים',
                'stat.orientations': 'כיוונים',
                'stat.degrees': 'מעלות',
                'stat.interval': 'מרווח',
                'section.ephemeris.title': 'ה<em>אפמריס</em>',
                'section.ephemeris.description': 'איפה השמש עכשיו? מחושב ממכניקה מסלולית.',
                'section.geometry.title': 'גאומטריית <em>חלונות</em>',
                'section.geometry.description': 'בית עם נוף. 11 תריסים. 4 כיוונים.',
                'section.weather.title': 'אינטגרציית <em>מזג אוויר</em>',
                'section.weather.description': 'חישובים שמימיים מניחים שמיים בהירים.',
                'section.triggers.title': 'טריגרים <em>שמימיים</em>',
                'section.triggers.description': 'אוטומציה מונעת אירועים.',
                'section.demo.title': 'הדגמה <em>חיה</em>',
                'section.demo.description': 'סימולציה אינטראקטיבית.',
                'section.architecture.title': 'ה<em>ארכיטקטורה</em>',
                'section.architecture.description': 'איך הכל מתחבר.',
                'label.azimuth': 'אזימוט',
                'label.altitude': 'גובה',
                'label.direction': 'כיוון',
                'label.isDay': 'יום',
                'label.weather': 'מזג אוויר',
                'label.cloudCoverage': 'כיסוי עננים',
                'demo.timeOfDay': 'שעה ביום',
                'demo.includeWeather': 'כלול מזג אוויר',
                'demo.sunPosition': 'מיקום השמש',
                'demo.shadeRecommendations': 'המלצות תריסים',
                'footer.title': 'מה עם מזג האוויר?',
                'footer.subtitle': 'היכן אסטרונומיה פוגשת נוחות ביתית',
                'yes': 'כן',
                'no': 'לא',
                
                // Compass & VR
                'compass.hint': 'הקש כדי להפעיל את כיוון המכשיר',
                'compass.hint.enabled': 'ההתמצאות הופעלה',
                'compass.orientationActive': 'מצפן פעיל — החוגה מאוזנת',
                'secret.info.title': 'מיקום סודי',
                'secret.info.subtitle': 'פרטים שנפתחו',
                'secret.info.revertTitle': 'חזרה למיקום שלך',
                'secret.info.revertSubtitle': 'המזג והגלובוס הותאמו לקואורדינטות שלך',
                'secret.info.teleportHome': 'ברוך הבא הביתה',
                'secret.info.teleportGeneric': 'עברת אל {location}',
                'secret.info.closeLabel': 'סגור מידע סודי',
                'weather.unknown': 'לא ידוע',
                'weather.sunrise': 'זריחה',
                'weather.sunset': 'שקיעה',
                'vr.enter': 'כניסה ל-VR',
                'vr.exit': 'יציאה מ-VR',
                'vr.enterAria': 'כניסה למצב VR חווייתי לצפייה בגופים שמימיים',
                'vr.exitAria': 'יציאה ממצב VR חווייתי'
            }
        };

        this.langNames = {
            en: { name: 'English', native: 'English', flag: '🇺🇸', dir: 'ltr' },
            es: { name: 'Spanish', native: 'Español', flag: '🇪🇸', dir: 'ltr' },
            ja: { name: 'Japanese', native: '日本語', flag: '🇯🇵', dir: 'ltr' },
            fr: { name: 'French', native: 'Français', flag: '🇫🇷', dir: 'ltr' },
            de: { name: 'German', native: 'Deutsch', flag: '🇩🇪', dir: 'ltr' },
            zh: { name: 'Chinese', native: '中文', flag: '🇨🇳', dir: 'ltr' },
            it: { name: 'Italian', native: 'Italiano', flag: '🇮🇹', dir: 'ltr' },
            pt: { name: 'Portuguese', native: 'Português', flag: '🇧🇷', dir: 'ltr' },
            ar: { name: 'Arabic', native: 'العربية', flag: '🇸🇦', dir: 'rtl' },
            he: { name: 'Hebrew', native: 'עברית', flag: '🇮🇱', dir: 'rtl' }
        };

        // RTL languages
        this.rtlLanguages = ['ar', 'he'];

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
     */
    get(key, params = {}) {
        let translation = this.translations[this.currentLang]?.[key]
            || this.translations[this.fallbackLang]?.[key]
            || key;

        Object.keys(params).forEach(param => {
            translation = translation.replace(new RegExp(`{${param}}`, 'g'), params[param]);
        });

        return translation;
    }

    /**
     * Set current language
     */
    setLang(lang) {
        if (!this.translations[lang]) {
            console.warn(`Language '${lang}' not supported.`);
            return false;
        }

        this.currentLang = lang;
        localStorage.setItem('preferredLanguage', lang);
        this.applyTranslations();
        
        // Set language and direction on document
        document.documentElement.lang = lang;
        const langInfo = this.langNames[lang];
        const dir = langInfo?.dir || 'ltr';
        document.documentElement.dir = dir;
        document.body.classList.toggle('rtl', dir === 'rtl');
        
        window.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang, dir } }));

        // Update selector UI
        this.updateSelectorUI();

        return true;
    }

    getCurrentLang() {
        return this.currentLang;
    }

    getAvailableLangs() {
        return Object.keys(this.translations);
    }

    /**
     * Apply translations to all elements
     */
    applyTranslations() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const translation = this.get(key);
            if (translation.includes('<')) {
                el.innerHTML = translation;
            } else {
                el.textContent = translation;
            }
        });

        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            el.placeholder = this.get(el.getAttribute('data-i18n-placeholder'));
        });

        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            el.title = this.get(el.getAttribute('data-i18n-title'));
        });

        document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
            el.setAttribute('aria-label', this.get(el.getAttribute('data-i18n-aria-label')));
        });
    }

    /**
     * Update the selector UI to reflect current language
     */
    updateSelectorUI() {
        const selector = document.querySelector('.lang-selector');
        if (!selector) return;

        const currentBtn = selector.querySelector('.lang-selector-current');
        if (currentBtn) {
            const info = this.langNames[this.currentLang];
            currentBtn.innerHTML = `<span class="lang-flag">${info.flag}</span><span class="lang-code">${this.currentLang.toUpperCase()}</span>`;
        }

        // Update active state in dropdown
        selector.querySelectorAll('.lang-option').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.lang === this.currentLang);
        });
    }

    /**
     * Create elegant language selector dropdown
     */
    createSelector() {
        const selector = document.createElement('div');
        selector.className = 'lang-selector';
        selector.setAttribute('role', 'combobox');
        selector.setAttribute('aria-label', 'Select language');
        selector.setAttribute('aria-expanded', 'false');
        selector.setAttribute('aria-haspopup', 'listbox');

        const currentInfo = this.langNames[this.currentLang];

        // Current language button
        const currentBtn = document.createElement('button');
        currentBtn.className = 'lang-selector-current';
        currentBtn.setAttribute('aria-label', `Current language: ${currentInfo.name}. Click to change.`);
        currentBtn.innerHTML = `
            <span class="lang-flag">${currentInfo.flag}</span>
            <span class="lang-code">${this.currentLang.toUpperCase()}</span>
            <svg class="lang-chevron" width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;

        // Dropdown menu
        const dropdown = document.createElement('div');
        dropdown.className = 'lang-dropdown';
        dropdown.setAttribute('role', 'listbox');

        const langs = Object.entries(this.langNames);
        langs.forEach(([code, info]) => {
            const option = document.createElement('button');
            option.className = `lang-option ${code === this.currentLang ? 'active' : ''}`;
            option.dataset.lang = code;
            option.setAttribute('role', 'option');
            option.setAttribute('aria-selected', code === this.currentLang);
            option.innerHTML = `
                <span class="lang-flag">${info.flag}</span>
                <span class="lang-native">${info.native}</span>
                <span class="lang-name">${info.name}</span>
            `;

            option.addEventListener('click', (e) => {
                e.stopPropagation();
                this.setLang(code);
                selector.classList.remove('open');
                selector.setAttribute('aria-expanded', 'false');
                if (typeof sound !== 'undefined' && sound.enabled) {
                    sound.playClick();
                }
            });

            dropdown.appendChild(option);
        });

        selector.appendChild(currentBtn);
        selector.appendChild(dropdown);

        // Toggle dropdown
        currentBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = selector.classList.toggle('open');
            selector.setAttribute('aria-expanded', isOpen);
        });

        // Close on click outside
        document.addEventListener('click', () => {
            selector.classList.remove('open');
            selector.setAttribute('aria-expanded', 'false');
        });

        // Close on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                selector.classList.remove('open');
                selector.setAttribute('aria-expanded', 'false');
            }
        });

        return selector;
    }

    /**
     * Initialize i18n
     */
    init() {
        document.documentElement.lang = this.currentLang;
        this.applyTranslations();

        // Add language selector to nav
        const navLinks = document.querySelector('.nav-links');
        if (navLinks) {
            const selector = this.createSelector();
            navLinks.appendChild(selector);
        }
    }
}

// Create global instance
const i18n = new I18n();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => i18n.init());
} else {
    i18n.init();
}
