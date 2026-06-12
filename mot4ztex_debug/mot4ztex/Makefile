CC=gcc 
#CFLAGS=$(shell pkg-config --cflags gtk+-3.0) -g -DDEBUG -DTESTGUI
CFLAGS=$(shell pkg-config --cflags gtk+-3.0) -g -Wall
LDFLAGS=-export-dynamic
LIBS=-lusb-1.0 -lm $(shell pkg-config --libs gtk+-3.0)

SRCS=main.c callbacks.c Compile.c DLList.c Format.c Functions.c \
	lex.yy.c parser.tab.c Run.c
OBJS=main.o callbacks.o Compile.o DLList.o Format.o Functions.o \
	lex.yy.o parser.tab.o Run.o
GUI=mot4

all: gmot4 tmot4

lex.yy.c: parser.tab.h lex.y
	flex lex.y

parser.tab.h: parser.tab.c 

parser.tab.c: parser.y
	bison  -d -t parser.y	

tmot4: gmot4
	@rm -f tmot4
	@ln -s gmot4 tmot4

gmot4: $(SRCS) $(OBJS) Types.h Functions.h
	$(CC) $(LDFLAGS) $(OBJS) -o gmot4 $(LIBS)

clean:
	rm $(OBJS) gmot4 tmot4
