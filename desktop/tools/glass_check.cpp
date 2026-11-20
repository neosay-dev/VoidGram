// Visual check of the Liquid Glass shader (voidgram_liquid_glass.cpp) without building the app:
//   g++ -std=c++20 -DVOIDGRAM_GLASS_STANDALONE -I <src>/Telegram/SourceFiles $(pkg-config --cflags Qt6Gui) \
//     desktop/tools/glass_check.cpp <src>/Telegram/SourceFiles/voidgram/voidgram_liquid_glass.cpp $(pkg-config --libs Qt6Gui) -o glass_check
//   QT_QPA_PLATFORM=offscreen ./glass_check glass.png
#include "voidgram/voidgram_liquid_glass.h"
#include <QtGui/QGuiApplication>
#include <QtGui/QPainter>
#include <QtGui/QLinearGradient>
#include <cassert>
int main(int argc, char **argv) {
	QGuiApplication app(argc, argv);
	// A busy backdrop: wallpaper gradient, text-like stripes and a coloured bubble, 3x scale.
	QImage page(900, 330, QImage::Format_ARGB32_Premultiplied);
	{
		QPainter p(&page);
		QLinearGradient g(0, 0, 900, 330); g.setColorAt(0, QColor(27, 42, 74)); g.setColorAt(1, QColor(58, 31, 61));
		p.fillRect(page.rect(), g);
		p.setPen(Qt::NoPen);
		for (int i = 0; i < 18; ++i) { p.setBrush(QColor(255, 255, 255, 140)); p.drawRect(40 + (i % 3) * 300, 20 + i * 17, 220 - (i % 4) * 30, 7); }
		p.setBrush(QColor(10, 132, 255)); p.drawRoundedRect(560, 180, 300, 110, 40, 40);
	}
	QImage out = page.copy();
	QPainter p(&out);
	const int sizes[] = { 120, 150, 120 };
	const QPoint spots[] = { QPoint(60, 100), QPoint(330, 90), QPoint(640, 170) };
	for (int i = 0; i < 3; ++i) {
		const QRect r(spots[i], QSize(sizes[i], sizes[i]));
		QImage glass = VoidGram::RenderLiquidGlass(page.copy(r), true);
		assert(glass.size() == r.size());
		assert(qAlpha(glass.pixel(0, 0)) == 0);             // outside the circle stays clear
		assert(qAlpha(glass.pixel(r.width() / 2, r.height() / 2)) == 255); // the middle is solid glass
		p.drawImage(r.topLeft(), glass);
	}
	p.end();
	out.save(argv[1]);
	return 0;
}
