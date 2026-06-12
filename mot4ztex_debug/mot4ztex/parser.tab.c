/* A Bison parser, made by GNU Bison 3.7.5.  */

/* Bison implementation for Yacc-like parsers in C

   Copyright (C) 1984, 1989-1990, 2000-2015, 2018-2021 Free Software Foundation,
   Inc.

   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <http://www.gnu.org/licenses/>.  */

/* As a special exception, you may create a larger work that contains
   part or all of the Bison parser skeleton and distribute that work
   under terms of your choice, so long as that work isn't itself a
   parser generator using the skeleton or a modified version thereof
   as a parser skeleton.  Alternatively, if you modify or redistribute
   the parser skeleton itself, you may (at your option) remove this
   special exception, which will cause the skeleton and the resulting
   Bison output files to be licensed under the GNU General Public
   License without this special exception.

   This special exception was added by the Free Software Foundation in
   version 2.2 of Bison.  */

/* C LALR(1) parser skeleton written by Richard Stallman, by
   simplifying the original so-called "semantic" parser.  */

/* DO NOT RELY ON FEATURES THAT ARE NOT DOCUMENTED in the manual,
   especially those whose name start with YY_ or yy_.  They are
   private implementation details that can be changed or removed.  */

/* All symbols defined below should begin with yy or YY, to avoid
   infringing on user name space.  This should be done even for local
   variables, as they might otherwise be expanded by user macros.
   There are some unavoidable exceptions within include files to
   define necessary library symbols; they are noted "INFRINGES ON
   USER NAME SPACE" below.  */

/* Identify Bison output, and Bison version.  */
#define YYBISON 30705

/* Bison version string.  */
#define YYBISON_VERSION "3.7.5"

/* Skeleton name.  */
#define YYSKELETON_NAME "yacc.c"

/* Pure parsers.  */
#define YYPURE 0

/* Push parsers.  */
#define YYPUSH 0

/* Pull parsers.  */
#define YYPULL 1




/* First part of user prologue.  */
#line 4 "parser.y"

#include<stdio.h>
#include<string.h>
#include<malloc.h>
#include<values.h>
#include<limits.h>
#include "Types.h"
#include "DLList.h"

#define MAXCMTSIZE 1000
char cmtline[MAXCMTSIZE];
prog *yypprog=NULL;         
extern int yylex();
int yyerror(char *);
 

#line 88 "parser.tab.c"

# ifndef YY_CAST
#  ifdef __cplusplus
#   define YY_CAST(Type, Val) static_cast<Type> (Val)
#   define YY_REINTERPRET_CAST(Type, Val) reinterpret_cast<Type> (Val)
#  else
#   define YY_CAST(Type, Val) ((Type) (Val))
#   define YY_REINTERPRET_CAST(Type, Val) ((Type) (Val))
#  endif
# endif
# ifndef YY_NULLPTR
#  if defined __cplusplus
#   if 201103L <= __cplusplus
#    define YY_NULLPTR nullptr
#   else
#    define YY_NULLPTR 0
#   endif
#  else
#   define YY_NULLPTR ((void*)0)
#  endif
# endif


/* Debug traces.  */
#ifndef YYDEBUG
# define YYDEBUG 0
#endif
#if YYDEBUG
extern int yydebug;
#endif

/* Token kinds.  */
#ifndef YYTOKENTYPE
# define YYTOKENTYPE
  enum yytokentype
  {
    YYEMPTY = -2,
    YYEOF = 0,                     /* "end of file"  */
    YYerror = 256,                 /* error  */
    YYUNDEF = 257,                 /* "invalid token"  */
    CODE = 258,                    /* CODE  */
    NUM = 259,                     /* NUM  */
    STATE = 260,                   /* STATE  */
    ADDR = 261,                    /* ADDR  */
    DATA = 262,                    /* DATA  */
    BIN = 263,                     /* BIN  */
    STP = 264,                     /* STP  */
    BL = 265,                      /* BL  */
    EL = 266,                      /* EL  */
    BC = 267,                      /* BC  */
    EC = 268,                      /* EC  */
    BI = 269,                      /* BI  */
    EI = 270,                      /* EI  */
    BN = 271,                      /* BN  */
    EN = 272,                      /* EN  */
    IT = 273,                      /* IT  */
    RMP = 274,                     /* RMP  */
    GFIB = 275,                    /* GFIB  */
    DISAB = 276,                   /* DISAB  */
    BR = 277,                      /* BR  */
    CHR = 278,                     /* CHR  */
    PARM = 279,                    /* PARM  */
    TIME = 280                     /* TIME  */
  };
  typedef enum yytokentype yytoken_kind_t;
#endif

/* Value type.  */
#if ! defined YYSTYPE && ! defined YYSTYPE_IS_DECLARED
union YYSTYPE
{
#line 21 "parser.y"

char cval;
char *sval;
unsigned ival;
unsigned bval;
long long lval;
double fval;
initact ia;
inneract na;
initlist *il;
innerlist *nl;
loop	lp;

#line 174 "parser.tab.c"

};
typedef union YYSTYPE YYSTYPE;
# define YYSTYPE_IS_TRIVIAL 1
# define YYSTYPE_IS_DECLARED 1
#endif


extern YYSTYPE yylval;

int yyparse (void);


/* Symbol kind.  */
enum yysymbol_kind_t
{
  YYSYMBOL_YYEMPTY = -2,
  YYSYMBOL_YYEOF = 0,                      /* "end of file"  */
  YYSYMBOL_YYerror = 1,                    /* error  */
  YYSYMBOL_YYUNDEF = 2,                    /* "invalid token"  */
  YYSYMBOL_CODE = 3,                       /* CODE  */
  YYSYMBOL_NUM = 4,                        /* NUM  */
  YYSYMBOL_STATE = 5,                      /* STATE  */
  YYSYMBOL_ADDR = 6,                       /* ADDR  */
  YYSYMBOL_DATA = 7,                       /* DATA  */
  YYSYMBOL_BIN = 8,                        /* BIN  */
  YYSYMBOL_STP = 9,                        /* STP  */
  YYSYMBOL_BL = 10,                        /* BL  */
  YYSYMBOL_EL = 11,                        /* EL  */
  YYSYMBOL_BC = 12,                        /* BC  */
  YYSYMBOL_EC = 13,                        /* EC  */
  YYSYMBOL_BI = 14,                        /* BI  */
  YYSYMBOL_EI = 15,                        /* EI  */
  YYSYMBOL_BN = 16,                        /* BN  */
  YYSYMBOL_EN = 17,                        /* EN  */
  YYSYMBOL_IT = 18,                        /* IT  */
  YYSYMBOL_RMP = 19,                       /* RMP  */
  YYSYMBOL_GFIB = 20,                      /* GFIB  */
  YYSYMBOL_DISAB = 21,                     /* DISAB  */
  YYSYMBOL_BR = 22,                        /* BR  */
  YYSYMBOL_CHR = 23,                       /* CHR  */
  YYSYMBOL_PARM = 24,                      /* PARM  */
  YYSYMBOL_TIME = 25,                      /* TIME  */
  YYSYMBOL_YYACCEPT = 26,                  /* $accept  */
  YYSYMBOL_input = 27,                     /* input  */
  YYSYMBOL_loop = 28,                      /* loop  */
  YYSYMBOL_loopbody = 29,                  /* loopbody  */
  YYSYMBOL_comment = 30,                   /* comment  */
  YYSYMBOL_commentbody = 31,               /* commentbody  */
  YYSYMBOL_init = 32,                      /* init  */
  YYSYMBOL_initbody = 33,                  /* initbody  */
  YYSYMBOL_inner = 34,                     /* inner  */
  YYSYMBOL_innerbody = 35,                 /* innerbody  */
  YYSYMBOL_iter = 36,                      /* iter  */
  YYSYMBOL_initline = 37,                  /* initline  */
  YYSYMBOL_ilbody = 38,                    /* ilbody  */
  YYSYMBOL_isimple = 39,                   /* isimple  */
  YYSYMBOL_ibinary = 40,                   /* ibinary  */
  YYSYMBOL_ienum = 41,                     /* ienum  */
  YYSYMBOL_iscalar = 42,                   /* iscalar  */
  YYSYMBOL_itest = 43,                     /* itest  */
  YYSYMBOL_innerline = 44,                 /* innerline  */
  YYSYMBOL_nlbody = 45,                    /* nlbody  */
  YYSYMBOL_nsimple = 46,                   /* nsimple  */
  YYSYMBOL_nbinary = 47,                   /* nbinary  */
  YYSYMBOL_nenum = 48,                     /* nenum  */
  YYSYMBOL_nscalar = 49,                   /* nscalar  */
  YYSYMBOL_ntest = 50,                     /* ntest  */
  YYSYMBOL_ramp = 51                       /* ramp  */
};
typedef enum yysymbol_kind_t yysymbol_kind_t;




#ifdef short
# undef short
#endif

/* On compilers that do not define __PTRDIFF_MAX__ etc., make sure
   <limits.h> and (if available) <stdint.h> are included
   so that the code can choose integer types of a good width.  */

#ifndef __PTRDIFF_MAX__
# include <limits.h> /* INFRINGES ON USER NAME SPACE */
# if defined __STDC_VERSION__ && 199901 <= __STDC_VERSION__
#  include <stdint.h> /* INFRINGES ON USER NAME SPACE */
#  define YY_STDINT_H
# endif
#endif

/* Narrow types that promote to a signed type and that can represent a
   signed or unsigned integer of at least N bits.  In tables they can
   save space and decrease cache pressure.  Promoting to a signed type
   helps avoid bugs in integer arithmetic.  */

#ifdef __INT_LEAST8_MAX__
typedef __INT_LEAST8_TYPE__ yytype_int8;
#elif defined YY_STDINT_H
typedef int_least8_t yytype_int8;
#else
typedef signed char yytype_int8;
#endif

#ifdef __INT_LEAST16_MAX__
typedef __INT_LEAST16_TYPE__ yytype_int16;
#elif defined YY_STDINT_H
typedef int_least16_t yytype_int16;
#else
typedef short yytype_int16;
#endif

/* Work around bug in HP-UX 11.23, which defines these macros
   incorrectly for preprocessor constants.  This workaround can likely
   be removed in 2023, as HPE has promised support for HP-UX 11.23
   (aka HP-UX 11i v2) only through the end of 2022; see Table 2 of
   <https://h20195.www2.hpe.com/V2/getpdf.aspx/4AA4-7673ENW.pdf>.  */
#ifdef __hpux
# undef UINT_LEAST8_MAX
# undef UINT_LEAST16_MAX
# define UINT_LEAST8_MAX 255
# define UINT_LEAST16_MAX 65535
#endif

#if defined __UINT_LEAST8_MAX__ && __UINT_LEAST8_MAX__ <= __INT_MAX__
typedef __UINT_LEAST8_TYPE__ yytype_uint8;
#elif (!defined __UINT_LEAST8_MAX__ && defined YY_STDINT_H \
       && UINT_LEAST8_MAX <= INT_MAX)
typedef uint_least8_t yytype_uint8;
#elif !defined __UINT_LEAST8_MAX__ && UCHAR_MAX <= INT_MAX
typedef unsigned char yytype_uint8;
#else
typedef short yytype_uint8;
#endif

#if defined __UINT_LEAST16_MAX__ && __UINT_LEAST16_MAX__ <= __INT_MAX__
typedef __UINT_LEAST16_TYPE__ yytype_uint16;
#elif (!defined __UINT_LEAST16_MAX__ && defined YY_STDINT_H \
       && UINT_LEAST16_MAX <= INT_MAX)
typedef uint_least16_t yytype_uint16;
#elif !defined __UINT_LEAST16_MAX__ && USHRT_MAX <= INT_MAX
typedef unsigned short yytype_uint16;
#else
typedef int yytype_uint16;
#endif

#ifndef YYPTRDIFF_T
# if defined __PTRDIFF_TYPE__ && defined __PTRDIFF_MAX__
#  define YYPTRDIFF_T __PTRDIFF_TYPE__
#  define YYPTRDIFF_MAXIMUM __PTRDIFF_MAX__
# elif defined PTRDIFF_MAX
#  ifndef ptrdiff_t
#   include <stddef.h> /* INFRINGES ON USER NAME SPACE */
#  endif
#  define YYPTRDIFF_T ptrdiff_t
#  define YYPTRDIFF_MAXIMUM PTRDIFF_MAX
# else
#  define YYPTRDIFF_T long
#  define YYPTRDIFF_MAXIMUM LONG_MAX
# endif
#endif

#ifndef YYSIZE_T
# ifdef __SIZE_TYPE__
#  define YYSIZE_T __SIZE_TYPE__
# elif defined size_t
#  define YYSIZE_T size_t
# elif defined __STDC_VERSION__ && 199901 <= __STDC_VERSION__
#  include <stddef.h> /* INFRINGES ON USER NAME SPACE */
#  define YYSIZE_T size_t
# else
#  define YYSIZE_T unsigned
# endif
#endif

#define YYSIZE_MAXIMUM                                  \
  YY_CAST (YYPTRDIFF_T,                                 \
           (YYPTRDIFF_MAXIMUM < YY_CAST (YYSIZE_T, -1)  \
            ? YYPTRDIFF_MAXIMUM                         \
            : YY_CAST (YYSIZE_T, -1)))

#define YYSIZEOF(X) YY_CAST (YYPTRDIFF_T, sizeof (X))


/* Stored state numbers (used for stacks). */
typedef yytype_int8 yy_state_t;

/* State numbers in computations.  */
typedef int yy_state_fast_t;

#ifndef YY_
# if defined YYENABLE_NLS && YYENABLE_NLS
#  if ENABLE_NLS
#   include <libintl.h> /* INFRINGES ON USER NAME SPACE */
#   define YY_(Msgid) dgettext ("bison-runtime", Msgid)
#  endif
# endif
# ifndef YY_
#  define YY_(Msgid) Msgid
# endif
#endif


#ifndef YY_ATTRIBUTE_PURE
# if defined __GNUC__ && 2 < __GNUC__ + (96 <= __GNUC_MINOR__)
#  define YY_ATTRIBUTE_PURE __attribute__ ((__pure__))
# else
#  define YY_ATTRIBUTE_PURE
# endif
#endif

#ifndef YY_ATTRIBUTE_UNUSED
# if defined __GNUC__ && 2 < __GNUC__ + (7 <= __GNUC_MINOR__)
#  define YY_ATTRIBUTE_UNUSED __attribute__ ((__unused__))
# else
#  define YY_ATTRIBUTE_UNUSED
# endif
#endif

/* Suppress unused-variable warnings by "using" E.  */
#if ! defined lint || defined __GNUC__
# define YY_USE(E) ((void) (E))
#else
# define YY_USE(E) /* empty */
#endif

#if defined __GNUC__ && ! defined __ICC && 407 <= __GNUC__ * 100 + __GNUC_MINOR__
/* Suppress an incorrect diagnostic about yylval being uninitialized.  */
# define YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN                            \
    _Pragma ("GCC diagnostic push")                                     \
    _Pragma ("GCC diagnostic ignored \"-Wuninitialized\"")              \
    _Pragma ("GCC diagnostic ignored \"-Wmaybe-uninitialized\"")
# define YY_IGNORE_MAYBE_UNINITIALIZED_END      \
    _Pragma ("GCC diagnostic pop")
#else
# define YY_INITIAL_VALUE(Value) Value
#endif
#ifndef YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
# define YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
# define YY_IGNORE_MAYBE_UNINITIALIZED_END
#endif
#ifndef YY_INITIAL_VALUE
# define YY_INITIAL_VALUE(Value) /* Nothing. */
#endif

#if defined __cplusplus && defined __GNUC__ && ! defined __ICC && 6 <= __GNUC__
# define YY_IGNORE_USELESS_CAST_BEGIN                          \
    _Pragma ("GCC diagnostic push")                            \
    _Pragma ("GCC diagnostic ignored \"-Wuseless-cast\"")
# define YY_IGNORE_USELESS_CAST_END            \
    _Pragma ("GCC diagnostic pop")
#endif
#ifndef YY_IGNORE_USELESS_CAST_BEGIN
# define YY_IGNORE_USELESS_CAST_BEGIN
# define YY_IGNORE_USELESS_CAST_END
#endif


#define YY_ASSERT(E) ((void) (0 && (E)))

#if !defined yyoverflow

/* The parser invokes alloca or malloc; define the necessary symbols.  */

# ifdef YYSTACK_USE_ALLOCA
#  if YYSTACK_USE_ALLOCA
#   ifdef __GNUC__
#    define YYSTACK_ALLOC __builtin_alloca
#   elif defined __BUILTIN_VA_ARG_INCR
#    include <alloca.h> /* INFRINGES ON USER NAME SPACE */
#   elif defined _AIX
#    define YYSTACK_ALLOC __alloca
#   elif defined _MSC_VER
#    include <malloc.h> /* INFRINGES ON USER NAME SPACE */
#    define alloca _alloca
#   else
#    define YYSTACK_ALLOC alloca
#    if ! defined _ALLOCA_H && ! defined EXIT_SUCCESS
#     include <stdlib.h> /* INFRINGES ON USER NAME SPACE */
      /* Use EXIT_SUCCESS as a witness for stdlib.h.  */
#     ifndef EXIT_SUCCESS
#      define EXIT_SUCCESS 0
#     endif
#    endif
#   endif
#  endif
# endif

# ifdef YYSTACK_ALLOC
   /* Pacify GCC's 'empty if-body' warning.  */
#  define YYSTACK_FREE(Ptr) do { /* empty */; } while (0)
#  ifndef YYSTACK_ALLOC_MAXIMUM
    /* The OS might guarantee only one guard page at the bottom of the stack,
       and a page size can be as small as 4096 bytes.  So we cannot safely
       invoke alloca (N) if N exceeds 4096.  Use a slightly smaller number
       to allow for a few compiler-allocated temporary stack slots.  */
#   define YYSTACK_ALLOC_MAXIMUM 4032 /* reasonable circa 2006 */
#  endif
# else
#  define YYSTACK_ALLOC YYMALLOC
#  define YYSTACK_FREE YYFREE
#  ifndef YYSTACK_ALLOC_MAXIMUM
#   define YYSTACK_ALLOC_MAXIMUM YYSIZE_MAXIMUM
#  endif
#  if (defined __cplusplus && ! defined EXIT_SUCCESS \
       && ! ((defined YYMALLOC || defined malloc) \
             && (defined YYFREE || defined free)))
#   include <stdlib.h> /* INFRINGES ON USER NAME SPACE */
#   ifndef EXIT_SUCCESS
#    define EXIT_SUCCESS 0
#   endif
#  endif
#  ifndef YYMALLOC
#   define YYMALLOC malloc
#   if ! defined malloc && ! defined EXIT_SUCCESS
void *malloc (YYSIZE_T); /* INFRINGES ON USER NAME SPACE */
#   endif
#  endif
#  ifndef YYFREE
#   define YYFREE free
#   if ! defined free && ! defined EXIT_SUCCESS
void free (void *); /* INFRINGES ON USER NAME SPACE */
#   endif
#  endif
# endif
#endif /* !defined yyoverflow */

#if (! defined yyoverflow \
     && (! defined __cplusplus \
         || (defined YYSTYPE_IS_TRIVIAL && YYSTYPE_IS_TRIVIAL)))

/* A type that is properly aligned for any stack member.  */
union yyalloc
{
  yy_state_t yyss_alloc;
  YYSTYPE yyvs_alloc;
};

/* The size of the maximum gap between one aligned stack and the next.  */
# define YYSTACK_GAP_MAXIMUM (YYSIZEOF (union yyalloc) - 1)

/* The size of an array large to enough to hold all stacks, each with
   N elements.  */
# define YYSTACK_BYTES(N) \
     ((N) * (YYSIZEOF (yy_state_t) + YYSIZEOF (YYSTYPE)) \
      + YYSTACK_GAP_MAXIMUM)

# define YYCOPY_NEEDED 1

/* Relocate STACK from its old location to the new one.  The
   local variables YYSIZE and YYSTACKSIZE give the old and new number of
   elements in the stack, and YYPTR gives the new location of the
   stack.  Advance YYPTR to a properly aligned location for the next
   stack.  */
# define YYSTACK_RELOCATE(Stack_alloc, Stack)                           \
    do                                                                  \
      {                                                                 \
        YYPTRDIFF_T yynewbytes;                                         \
        YYCOPY (&yyptr->Stack_alloc, Stack, yysize);                    \
        Stack = &yyptr->Stack_alloc;                                    \
        yynewbytes = yystacksize * YYSIZEOF (*Stack) + YYSTACK_GAP_MAXIMUM; \
        yyptr += yynewbytes / YYSIZEOF (*yyptr);                        \
      }                                                                 \
    while (0)

#endif

#if defined YYCOPY_NEEDED && YYCOPY_NEEDED
/* Copy COUNT objects from SRC to DST.  The source and destination do
   not overlap.  */
# ifndef YYCOPY
#  if defined __GNUC__ && 1 < __GNUC__
#   define YYCOPY(Dst, Src, Count) \
      __builtin_memcpy (Dst, Src, YY_CAST (YYSIZE_T, (Count)) * sizeof (*(Src)))
#  else
#   define YYCOPY(Dst, Src, Count)              \
      do                                        \
        {                                       \
          YYPTRDIFF_T yyi;                      \
          for (yyi = 0; yyi < (Count); yyi++)   \
            (Dst)[yyi] = (Src)[yyi];            \
        }                                       \
      while (0)
#  endif
# endif
#endif /* !YYCOPY_NEEDED */

/* YYFINAL -- State number of the termination state.  */
#define YYFINAL  2
/* YYLAST -- Last index in YYTABLE.  */
#define YYLAST   76

/* YYNTOKENS -- Number of terminals.  */
#define YYNTOKENS  26
/* YYNNTS -- Number of nonterminals.  */
#define YYNNTS  26
/* YYNRULES -- Number of rules.  */
#define YYNRULES  52
/* YYNSTATES -- Number of states.  */
#define YYNSTATES  87

/* YYMAXUTOK -- Last valid token kind.  */
#define YYMAXUTOK   280


/* YYTRANSLATE(TOKEN-NUM) -- Symbol number corresponding to TOKEN-NUM
   as returned by yylex, with out-of-bounds checking.  */
#define YYTRANSLATE(YYX)                                \
  (0 <= (YYX) && (YYX) <= YYMAXUTOK                     \
   ? YY_CAST (yysymbol_kind_t, yytranslate[YYX])        \
   : YYSYMBOL_YYUNDEF)

/* YYTRANSLATE[TOKEN-NUM] -- Symbol number corresponding to TOKEN-NUM
   as returned by yylex.  */
static const yytype_int8 yytranslate[] =
{
       0,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     1,     2,     3,     4,
       5,     6,     7,     8,     9,    10,    11,    12,    13,    14,
      15,    16,    17,    18,    19,    20,    21,    22,    23,    24,
      25
};

#if YYDEBUG
  /* YYRLINE[YYN] -- Source line where rule number YYN was defined.  */
static const yytype_uint8 yyrline[] =
{
       0,    51,    51,    52,    55,    56,    59,    63,    67,    71,
      75,    79,    83,    86,    91,    94,    95,    99,   102,   103,
     106,   109,   110,   113,   116,   117,   118,   121,   122,   123,
     124,   125,   128,   133,   139,   145,   150,   157,   158,   159,
     162,   163,   164,   165,   166,   167,   170,   178,   186,   195,
     202,   213,   220
};
#endif

/** Accessing symbol of state STATE.  */
#define YY_ACCESSING_SYMBOL(State) YY_CAST (yysymbol_kind_t, yystos[State])

#if YYDEBUG || 0
/* The user-facing name of the symbol whose (internal) number is
   YYSYMBOL.  No bounds checking.  */
static const char *yysymbol_name (yysymbol_kind_t yysymbol) YY_ATTRIBUTE_UNUSED;

/* YYTNAME[SYMBOL-NUM] -- String name of the symbol SYMBOL-NUM.
   First, the terminals, then, starting at YYNTOKENS, nonterminals.  */
static const char *const yytname[] =
{
  "\"end of file\"", "error", "\"invalid token\"", "CODE", "NUM", "STATE",
  "ADDR", "DATA", "BIN", "STP", "BL", "EL", "BC", "EC", "BI", "EI", "BN",
  "EN", "IT", "RMP", "GFIB", "DISAB", "BR", "CHR", "PARM", "TIME",
  "$accept", "input", "loop", "loopbody", "comment", "commentbody", "init",
  "initbody", "inner", "innerbody", "iter", "initline", "ilbody",
  "isimple", "ibinary", "ienum", "iscalar", "itest", "innerline", "nlbody",
  "nsimple", "nbinary", "nenum", "nscalar", "ntest", "ramp", YY_NULLPTR
};

static const char *
yysymbol_name (yysymbol_kind_t yysymbol)
{
  return yytname[yysymbol];
}
#endif

#ifdef YYPRINT
/* YYTOKNUM[NUM] -- (External) token number corresponding to the
   (internal) symbol number NUM (which must be that of a token).  */
static const yytype_int16 yytoknum[] =
{
       0,   256,   257,   258,   259,   260,   261,   262,   263,   264,
     265,   266,   267,   268,   269,   270,   271,   272,   273,   274,
     275,   276,   277,   278,   279,   280
};
#endif

#define YYPACT_NINF (-22)

#define yypact_value_is_default(Yyn) \
  ((Yyn) == YYPACT_NINF)

#define YYTABLE_NINF (-1)

#define yytable_value_is_error(Yyn) \
  0

  /* YYPACT[STATE-NUM] -- Index in YYTABLE of the portion describing
     STATE-NUM.  */
static const yytype_int8 yypact[] =
{
     -22,     5,   -22,    25,   -22,   -22,    27,   -21,    36,    -1,
      -7,    22,    -5,    13,   -22,    16,    28,    10,    40,     3,
     -22,    23,   -22,   -22,   -22,   -22,   -22,     9,    17,   -22,
      34,    38,   -22,    22,    -5,    49,    -5,   -22,   -22,   -22,
     -22,   -22,   -22,    50,   -22,   -22,   -22,   -22,   -22,   -22,
      55,    56,    -4,    54,    58,   -22,   -22,   -22,   -22,   -22,
     -22,   -22,   -22,   -22,   -22,   -22,    -5,   -22,   -22,   -22,
     -22,    59,   -22,   -22,    39,    41,    60,   -22,   -22,   -22,
      62,    61,    65,   -22,    66,   -22,   -22
};

  /* YYDEFACT[STATE-NUM] -- Default reduction number in state STATE-NUM.
     Performed when YYTABLE does not specify something else to do.  Zero
     means the default is an error.  */
static const yytype_int8 yydefact[] =
{
       2,     0,     1,     0,     3,    15,     0,     0,     0,     0,
       0,    13,     0,     0,    32,     0,     0,     0,     0,     0,
      18,    26,    30,    27,    28,    29,    31,     0,     0,    21,
      39,     0,     4,    12,     0,     0,     0,    11,     9,    14,
      16,    34,    33,     0,    35,    17,    19,    24,    25,    46,
       0,     0,     0,     0,     0,    44,    40,    41,    43,    45,
      42,    20,    22,    37,    38,     5,     0,    10,     8,    23,
       7,     0,    48,    47,     0,     0,     0,    49,     6,    36,
       0,     0,     0,    52,     0,    50,    51
};

  /* YYPGOTO[NTERM-NUM].  */
static const yytype_int8 yypgoto[] =
{
     -22,   -22,   -22,    63,   -22,   -22,    53,   -22,    -8,   -22,
     -12,    57,   -22,   -22,   -22,   -22,   -22,   -22,    44,   -22,
     -22,   -22,   -22,   -22,   -22,   -22
};

  /* YYDEFGOTO[NTERM-NUM].  */
static const yytype_int8 yydefgoto[] =
{
       0,     1,     4,     9,    10,    13,    11,    19,    12,    28,
      37,    20,    21,    22,    23,    24,    25,    26,    29,    30,
      55,    56,    57,    58,    59,    60
};

  /* YYTABLE[YYPACT[STATE-NUM]] -- What to do in state STATE-NUM.  If
     positive, shift that token.  If negative, reduce the rule whose
     number is the opposite.  If YYTABLE_NINF, syntax error.  */
static const yytype_int8 yytable[] =
{
      38,    74,    34,    36,    27,     2,    14,     6,    15,     7,
      32,    16,    49,    35,    50,     3,    43,    51,    45,    41,
      75,    67,    68,    17,    70,    66,    39,    18,    52,    53,
      14,    42,    15,    54,    61,    16,    40,     5,     7,     6,
      35,     7,    27,    44,    47,    48,     8,    17,     5,    65,
       6,    18,     7,    69,    78,    63,    64,    71,    72,    73,
      76,    77,    79,    33,    80,    83,    81,    82,    85,    86,
      84,    31,    62,     0,     0,     0,    46
};

static const yytype_int8 yycheck[] =
{
      12,     5,    10,    11,    25,     0,     3,    14,     5,    16,
      11,     8,     3,    18,     5,    10,     6,     8,    15,     3,
      24,    33,    34,    20,    36,    33,    13,    24,    19,    20,
       3,     3,     5,    24,    17,     8,    23,    12,    16,    14,
      18,    16,    25,     3,    21,    22,    21,    20,    12,    11,
      14,    24,    16,     4,    66,    21,    22,     7,     3,     3,
       6,     3,     3,    10,    25,     3,    25,     7,     3,     3,
       9,     8,    28,    -1,    -1,    -1,    19
};

  /* YYSTOS[STATE-NUM] -- The (internal number of the) accessing
     symbol of state STATE-NUM.  */
static const yytype_int8 yystos[] =
{
       0,    27,     0,    10,    28,    12,    14,    16,    21,    29,
      30,    32,    34,    31,     3,     5,     8,    20,    24,    33,
      37,    38,    39,    40,    41,    42,    43,    25,    35,    44,
      45,    29,    11,    32,    34,    18,    34,    36,    36,    13,
      23,     3,     3,     6,     3,    15,    37,    21,    22,     3,
       5,     8,    19,    20,    24,    46,    47,    48,    49,    50,
      51,    17,    44,    21,    22,    11,    34,    36,    36,     4,
      36,     7,     3,     3,     5,    24,     6,     3,    36,     3,
      25,    25,     7,     3,     9,     3,     3
};

  /* YYR1[YYN] -- Symbol number of symbol that rule YYN derives.  */
static const yytype_int8 yyr1[] =
{
       0,    26,    27,    27,    28,    28,    29,    29,    29,    29,
      29,    29,    29,    29,    30,    31,    31,    32,    33,    33,
      34,    35,    35,    36,    37,    37,    37,    38,    38,    38,
      38,    38,    39,    40,    41,    42,    43,    44,    44,    44,
      45,    45,    45,    45,    45,    45,    46,    47,    48,    49,
      50,    51,    51
};

  /* YYR2[YYN] -- Number of symbols on the right hand side of rule YYN.  */
static const yytype_int8 yyr2[] =
{
       0,     2,     0,     2,     3,     4,     4,     3,     3,     2,
       3,     2,     2,     1,     3,     0,     2,     3,     1,     2,
       3,     1,     2,     2,     2,     2,     1,     1,     1,     1,
       1,     1,     1,     2,     2,     2,     4,     2,     2,     1,
       2,     2,     2,     2,     2,     2,     1,     2,     2,     2,
       4,     5,     4
};


enum { YYENOMEM = -2 };

#define yyerrok         (yyerrstatus = 0)
#define yyclearin       (yychar = YYEMPTY)

#define YYACCEPT        goto yyacceptlab
#define YYABORT         goto yyabortlab
#define YYERROR         goto yyerrorlab


#define YYRECOVERING()  (!!yyerrstatus)

#define YYBACKUP(Token, Value)                                    \
  do                                                              \
    if (yychar == YYEMPTY)                                        \
      {                                                           \
        yychar = (Token);                                         \
        yylval = (Value);                                         \
        YYPOPSTACK (yylen);                                       \
        yystate = *yyssp;                                         \
        goto yybackup;                                            \
      }                                                           \
    else                                                          \
      {                                                           \
        yyerror (YY_("syntax error: cannot back up")); \
        YYERROR;                                                  \
      }                                                           \
  while (0)

/* Backward compatibility with an undocumented macro.
   Use YYerror or YYUNDEF. */
#define YYERRCODE YYUNDEF


/* Enable debugging if requested.  */
#if YYDEBUG

# ifndef YYFPRINTF
#  include <stdio.h> /* INFRINGES ON USER NAME SPACE */
#  define YYFPRINTF fprintf
# endif

# define YYDPRINTF(Args)                        \
do {                                            \
  if (yydebug)                                  \
    YYFPRINTF Args;                             \
} while (0)

/* This macro is provided for backward compatibility. */
# ifndef YY_LOCATION_PRINT
#  define YY_LOCATION_PRINT(File, Loc) ((void) 0)
# endif


# define YY_SYMBOL_PRINT(Title, Kind, Value, Location)                    \
do {                                                                      \
  if (yydebug)                                                            \
    {                                                                     \
      YYFPRINTF (stderr, "%s ", Title);                                   \
      yy_symbol_print (stderr,                                            \
                  Kind, Value); \
      YYFPRINTF (stderr, "\n");                                           \
    }                                                                     \
} while (0)


/*-----------------------------------.
| Print this symbol's value on YYO.  |
`-----------------------------------*/

static void
yy_symbol_value_print (FILE *yyo,
                       yysymbol_kind_t yykind, YYSTYPE const * const yyvaluep)
{
  FILE *yyoutput = yyo;
  YY_USE (yyoutput);
  if (!yyvaluep)
    return;
# ifdef YYPRINT
  if (yykind < YYNTOKENS)
    YYPRINT (yyo, yytoknum[yykind], *yyvaluep);
# endif
  YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
  YY_USE (yykind);
  YY_IGNORE_MAYBE_UNINITIALIZED_END
}


/*---------------------------.
| Print this symbol on YYO.  |
`---------------------------*/

static void
yy_symbol_print (FILE *yyo,
                 yysymbol_kind_t yykind, YYSTYPE const * const yyvaluep)
{
  YYFPRINTF (yyo, "%s %s (",
             yykind < YYNTOKENS ? "token" : "nterm", yysymbol_name (yykind));

  yy_symbol_value_print (yyo, yykind, yyvaluep);
  YYFPRINTF (yyo, ")");
}

/*------------------------------------------------------------------.
| yy_stack_print -- Print the state stack from its BOTTOM up to its |
| TOP (included).                                                   |
`------------------------------------------------------------------*/

static void
yy_stack_print (yy_state_t *yybottom, yy_state_t *yytop)
{
  YYFPRINTF (stderr, "Stack now");
  for (; yybottom <= yytop; yybottom++)
    {
      int yybot = *yybottom;
      YYFPRINTF (stderr, " %d", yybot);
    }
  YYFPRINTF (stderr, "\n");
}

# define YY_STACK_PRINT(Bottom, Top)                            \
do {                                                            \
  if (yydebug)                                                  \
    yy_stack_print ((Bottom), (Top));                           \
} while (0)


/*------------------------------------------------.
| Report that the YYRULE is going to be reduced.  |
`------------------------------------------------*/

static void
yy_reduce_print (yy_state_t *yyssp, YYSTYPE *yyvsp,
                 int yyrule)
{
  int yylno = yyrline[yyrule];
  int yynrhs = yyr2[yyrule];
  int yyi;
  YYFPRINTF (stderr, "Reducing stack by rule %d (line %d):\n",
             yyrule - 1, yylno);
  /* The symbols being reduced.  */
  for (yyi = 0; yyi < yynrhs; yyi++)
    {
      YYFPRINTF (stderr, "   $%d = ", yyi + 1);
      yy_symbol_print (stderr,
                       YY_ACCESSING_SYMBOL (+yyssp[yyi + 1 - yynrhs]),
                       &yyvsp[(yyi + 1) - (yynrhs)]);
      YYFPRINTF (stderr, "\n");
    }
}

# define YY_REDUCE_PRINT(Rule)          \
do {                                    \
  if (yydebug)                          \
    yy_reduce_print (yyssp, yyvsp, Rule); \
} while (0)

/* Nonzero means print parse trace.  It is left uninitialized so that
   multiple parsers can coexist.  */
int yydebug;
#else /* !YYDEBUG */
# define YYDPRINTF(Args) ((void) 0)
# define YY_SYMBOL_PRINT(Title, Kind, Value, Location)
# define YY_STACK_PRINT(Bottom, Top)
# define YY_REDUCE_PRINT(Rule)
#endif /* !YYDEBUG */


/* YYINITDEPTH -- initial size of the parser's stacks.  */
#ifndef YYINITDEPTH
# define YYINITDEPTH 200
#endif

/* YYMAXDEPTH -- maximum size the stacks can grow to (effective only
   if the built-in stack extension method is used).

   Do not make this value too large; the results are undefined if
   YYSTACK_ALLOC_MAXIMUM < YYSTACK_BYTES (YYMAXDEPTH)
   evaluated with infinite-precision integer arithmetic.  */

#ifndef YYMAXDEPTH
# define YYMAXDEPTH 10000
#endif






/*-----------------------------------------------.
| Release the memory associated to this symbol.  |
`-----------------------------------------------*/

static void
yydestruct (const char *yymsg,
            yysymbol_kind_t yykind, YYSTYPE *yyvaluep)
{
  YY_USE (yyvaluep);
  if (!yymsg)
    yymsg = "Deleting";
  YY_SYMBOL_PRINT (yymsg, yykind, yyvaluep, yylocationp);

  YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
  YY_USE (yykind);
  YY_IGNORE_MAYBE_UNINITIALIZED_END
}


/* Lookahead token kind.  */
int yychar;

/* The semantic value of the lookahead symbol.  */
YYSTYPE yylval;
/* Number of syntax errors so far.  */
int yynerrs;




/*----------.
| yyparse.  |
`----------*/

int
yyparse (void)
{
    yy_state_fast_t yystate = 0;
    /* Number of tokens to shift before error messages enabled.  */
    int yyerrstatus = 0;

    /* Refer to the stacks through separate pointers, to allow yyoverflow
       to reallocate them elsewhere.  */

    /* Their size.  */
    YYPTRDIFF_T yystacksize = YYINITDEPTH;

    /* The state stack: array, bottom, top.  */
    yy_state_t yyssa[YYINITDEPTH];
    yy_state_t *yyss = yyssa;
    yy_state_t *yyssp = yyss;

    /* The semantic value stack: array, bottom, top.  */
    YYSTYPE yyvsa[YYINITDEPTH];
    YYSTYPE *yyvs = yyvsa;
    YYSTYPE *yyvsp = yyvs;

  int yyn;
  /* The return value of yyparse.  */
  int yyresult;
  /* Lookahead symbol kind.  */
  yysymbol_kind_t yytoken = YYSYMBOL_YYEMPTY;
  /* The variables used to return semantic value and location from the
     action routines.  */
  YYSTYPE yyval;



#define YYPOPSTACK(N)   (yyvsp -= (N), yyssp -= (N))

  /* The number of symbols on the RHS of the reduced rule.
     Keep to zero when no symbol should be popped.  */
  int yylen = 0;

  YYDPRINTF ((stderr, "Starting parse\n"));

  yychar = YYEMPTY; /* Cause a token to be read.  */
  goto yysetstate;


/*------------------------------------------------------------.
| yynewstate -- push a new state, which is found in yystate.  |
`------------------------------------------------------------*/
yynewstate:
  /* In all cases, when you get here, the value and location stacks
     have just been pushed.  So pushing a state here evens the stacks.  */
  yyssp++;


/*--------------------------------------------------------------------.
| yysetstate -- set current state (the top of the stack) to yystate.  |
`--------------------------------------------------------------------*/
yysetstate:
  YYDPRINTF ((stderr, "Entering state %d\n", yystate));
  YY_ASSERT (0 <= yystate && yystate < YYNSTATES);
  YY_IGNORE_USELESS_CAST_BEGIN
  *yyssp = YY_CAST (yy_state_t, yystate);
  YY_IGNORE_USELESS_CAST_END
  YY_STACK_PRINT (yyss, yyssp);

  if (yyss + yystacksize - 1 <= yyssp)
#if !defined yyoverflow && !defined YYSTACK_RELOCATE
    goto yyexhaustedlab;
#else
    {
      /* Get the current used size of the three stacks, in elements.  */
      YYPTRDIFF_T yysize = yyssp - yyss + 1;

# if defined yyoverflow
      {
        /* Give user a chance to reallocate the stack.  Use copies of
           these so that the &'s don't force the real ones into
           memory.  */
        yy_state_t *yyss1 = yyss;
        YYSTYPE *yyvs1 = yyvs;

        /* Each stack pointer address is followed by the size of the
           data in use in that stack, in bytes.  This used to be a
           conditional around just the two extra args, but that might
           be undefined if yyoverflow is a macro.  */
        yyoverflow (YY_("memory exhausted"),
                    &yyss1, yysize * YYSIZEOF (*yyssp),
                    &yyvs1, yysize * YYSIZEOF (*yyvsp),
                    &yystacksize);
        yyss = yyss1;
        yyvs = yyvs1;
      }
# else /* defined YYSTACK_RELOCATE */
      /* Extend the stack our own way.  */
      if (YYMAXDEPTH <= yystacksize)
        goto yyexhaustedlab;
      yystacksize *= 2;
      if (YYMAXDEPTH < yystacksize)
        yystacksize = YYMAXDEPTH;

      {
        yy_state_t *yyss1 = yyss;
        union yyalloc *yyptr =
          YY_CAST (union yyalloc *,
                   YYSTACK_ALLOC (YY_CAST (YYSIZE_T, YYSTACK_BYTES (yystacksize))));
        if (! yyptr)
          goto yyexhaustedlab;
        YYSTACK_RELOCATE (yyss_alloc, yyss);
        YYSTACK_RELOCATE (yyvs_alloc, yyvs);
#  undef YYSTACK_RELOCATE
        if (yyss1 != yyssa)
          YYSTACK_FREE (yyss1);
      }
# endif

      yyssp = yyss + yysize - 1;
      yyvsp = yyvs + yysize - 1;

      YY_IGNORE_USELESS_CAST_BEGIN
      YYDPRINTF ((stderr, "Stack size increased to %ld\n",
                  YY_CAST (long, yystacksize)));
      YY_IGNORE_USELESS_CAST_END

      if (yyss + yystacksize - 1 <= yyssp)
        YYABORT;
    }
#endif /* !defined yyoverflow && !defined YYSTACK_RELOCATE */

  if (yystate == YYFINAL)
    YYACCEPT;

  goto yybackup;


/*-----------.
| yybackup.  |
`-----------*/
yybackup:
  /* Do appropriate processing given the current state.  Read a
     lookahead token if we need one and don't already have one.  */

  /* First try to decide what to do without reference to lookahead token.  */
  yyn = yypact[yystate];
  if (yypact_value_is_default (yyn))
    goto yydefault;

  /* Not known => get a lookahead token if don't already have one.  */

  /* YYCHAR is either empty, or end-of-input, or a valid lookahead.  */
  if (yychar == YYEMPTY)
    {
      YYDPRINTF ((stderr, "Reading a token\n"));
      yychar = yylex ();
    }

  if (yychar <= YYEOF)
    {
      yychar = YYEOF;
      yytoken = YYSYMBOL_YYEOF;
      YYDPRINTF ((stderr, "Now at end of input.\n"));
    }
  else if (yychar == YYerror)
    {
      /* The scanner already issued an error message, process directly
         to error recovery.  But do not keep the error token as
         lookahead, it is too special and may lead us to an endless
         loop in error recovery. */
      yychar = YYUNDEF;
      yytoken = YYSYMBOL_YYerror;
      goto yyerrlab1;
    }
  else
    {
      yytoken = YYTRANSLATE (yychar);
      YY_SYMBOL_PRINT ("Next token is", yytoken, &yylval, &yylloc);
    }

  /* If the proper action on seeing token YYTOKEN is to reduce or to
     detect an error, take that action.  */
  yyn += yytoken;
  if (yyn < 0 || YYLAST < yyn || yycheck[yyn] != yytoken)
    goto yydefault;
  yyn = yytable[yyn];
  if (yyn <= 0)
    {
      if (yytable_value_is_error (yyn))
        goto yyerrlab;
      yyn = -yyn;
      goto yyreduce;
    }

  /* Count tokens shifted since error; after three, turn off error
     status.  */
  if (yyerrstatus)
    yyerrstatus--;

  /* Shift the lookahead token.  */
  YY_SYMBOL_PRINT ("Shifting", yytoken, &yylval, &yylloc);
  yystate = yyn;
  YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
  *++yyvsp = yylval;
  YY_IGNORE_MAYBE_UNINITIALIZED_END

  /* Discard the shifted token.  */
  yychar = YYEMPTY;
  goto yynewstate;


/*-----------------------------------------------------------.
| yydefault -- do the default action for the current state.  |
`-----------------------------------------------------------*/
yydefault:
  yyn = yydefact[yystate];
  if (yyn == 0)
    goto yyerrlab;
  goto yyreduce;


/*-----------------------------.
| yyreduce -- do a reduction.  |
`-----------------------------*/
yyreduce:
  /* yyn is the number of a rule to reduce with.  */
  yylen = yyr2[yyn];

  /* If YYLEN is nonzero, implement the default value of the action:
     '$$ = $1'.

     Otherwise, the following line sets YYVAL to garbage.
     This behavior is undocumented and Bison
     users should not rely upon it.  Assigning to YYVAL
     unconditionally makes the parser a bit smaller, and it avoids a
     GCC warning that YYVAL may be used uninitialized.  */
  yyval = yyvsp[1-yylen];


  YY_REDUCE_PRINT (yyn);
  switch (yyn)
    {
  case 3: /* input: input loop  */
#line 52 "parser.y"
                     {yypprog=PInsert(yypprog,(yyvsp[0].lp));}
#line 1262 "parser.tab.c"
    break;

  case 4: /* loop: BL loopbody EL  */
#line 55 "parser.y"
                                 {(yyval.lp) = (yyvsp[-1].lp); (yyval.lp).en = TRUE;}
#line 1268 "parser.tab.c"
    break;

  case 5: /* loop: BL DISAB loopbody EL  */
#line 56 "parser.y"
                                 {(yyval.lp) = (yyvsp[-1].lp); (yyval.lp).en = FALSE;}
#line 1274 "parser.tab.c"
    break;

  case 6: /* loopbody: comment init inner iter  */
#line 59 "parser.y"
                                  {(yyval.lp).cmt = (yyvsp[-3].sval); 
				   (yyval.lp).il = (yyvsp[-2].il); 
                                   (yyval.lp).nl = (yyvsp[-1].nl);
				   (yyval.lp).iter = (yyvsp[0].ival);}
#line 1283 "parser.tab.c"
    break;

  case 7: /* loopbody: init inner iter  */
#line 63 "parser.y"
                                   {(yyval.lp).cmt = NULL; 
				   (yyval.lp).il = (yyvsp[-2].il); 
                                   (yyval.lp).nl = (yyvsp[-1].nl);
				   (yyval.lp).iter = (yyvsp[0].ival);}
#line 1292 "parser.tab.c"
    break;

  case 8: /* loopbody: comment inner iter  */
#line 67 "parser.y"
                                   {(yyval.lp).cmt = (yyvsp[-2].sval); 
				   (yyval.lp).il = NULL; 
                                   (yyval.lp).nl = (yyvsp[-1].nl);
				   (yyval.lp).iter = (yyvsp[0].ival);}
#line 1301 "parser.tab.c"
    break;

  case 9: /* loopbody: inner iter  */
#line 71 "parser.y"
                                   {(yyval.lp).cmt = NULL; 
				   (yyval.lp).il = NULL; 
                                   (yyval.lp).nl = (yyvsp[-1].nl);
				   (yyval.lp).iter = (yyvsp[0].ival);}
#line 1310 "parser.tab.c"
    break;

  case 10: /* loopbody: comment init iter  */
#line 75 "parser.y"
                                   {(yyval.lp).cmt = (yyvsp[-2].sval); 
				   (yyval.lp).il = (yyvsp[-1].il); 
                                   (yyval.lp).nl = NULL;
				   (yyval.lp).iter = (yyvsp[0].ival);}
#line 1319 "parser.tab.c"
    break;

  case 11: /* loopbody: init iter  */
#line 79 "parser.y"
                                   {(yyval.lp).cmt = NULL; 
				   (yyval.lp).il = (yyvsp[-1].il); 
                                   (yyval.lp).nl = NULL;
				   (yyval.lp).iter = (yyvsp[0].ival);}
#line 1328 "parser.tab.c"
    break;

  case 12: /* loopbody: comment init  */
#line 83 "parser.y"
                                   {(yyval.lp).cmt = (yyvsp[-1].sval); 
				   (yyval.lp).il = (yyvsp[0].il); 
                                   (yyval.lp).nl = NULL;}
#line 1336 "parser.tab.c"
    break;

  case 13: /* loopbody: init  */
#line 86 "parser.y"
                                   {(yyval.lp).cmt = NULL; 
				   (yyval.lp).il = (yyvsp[0].il); 
                                   (yyval.lp).nl = NULL;}
#line 1344 "parser.tab.c"
    break;

  case 14: /* comment: BC commentbody EC  */
#line 91 "parser.y"
                           {*(yyvsp[-1].sval)='\0'; (yyval.sval)=strdup(cmtline);}
#line 1350 "parser.tab.c"
    break;

  case 15: /* commentbody: %empty  */
#line 94 "parser.y"
                                 {(yyval.sval)=cmtline;}
#line 1356 "parser.tab.c"
    break;

  case 16: /* commentbody: commentbody CHR  */
#line 95 "parser.y"
                                 {*(yyval.sval)=(yyvsp[0].cval); (yyval.sval)++;}
#line 1362 "parser.tab.c"
    break;

  case 17: /* init: BI initbody EI  */
#line 99 "parser.y"
                                 {(yyval.il) = (yyvsp[-1].il); }
#line 1368 "parser.tab.c"
    break;

  case 18: /* initbody: initline  */
#line 102 "parser.y"
                             {(yyval.il)=IInsert(NULL,(yyvsp[0].ia));}
#line 1374 "parser.tab.c"
    break;

  case 19: /* initbody: initbody initline  */
#line 103 "parser.y"
                             {(yyval.il)=IInsert((yyvsp[-1].il),(yyvsp[0].ia));}
#line 1380 "parser.tab.c"
    break;

  case 20: /* inner: BN innerbody EN  */
#line 106 "parser.y"
                             {(yyval.nl) = (yyvsp[-1].nl);}
#line 1386 "parser.tab.c"
    break;

  case 21: /* innerbody: innerline  */
#line 109 "parser.y"
                                 {(yyval.nl)=NInsert(NULL,(yyvsp[0].na));}
#line 1392 "parser.tab.c"
    break;

  case 22: /* innerbody: innerbody innerline  */
#line 110 "parser.y"
                                 {(yyval.nl)=NInsert((yyvsp[-1].nl),(yyvsp[0].na));}
#line 1398 "parser.tab.c"
    break;

  case 23: /* iter: IT NUM  */
#line 113 "parser.y"
                             {(yyval.ival) = (yyvsp[0].ival);}
#line 1404 "parser.tab.c"
    break;

  case 24: /* initline: ilbody DISAB  */
#line 116 "parser.y"
                             {(yyval.ia) = (yyvsp[-1].ia); (yyval.ia).block=FALSE; (yyval.ia).en = FALSE;}
#line 1410 "parser.tab.c"
    break;

  case 25: /* initline: ilbody BR  */
#line 117 "parser.y"
                             {(yyval.ia) = (yyvsp[-1].ia); (yyval.ia).block=TRUE;  (yyval.ia).en = TRUE;}
#line 1416 "parser.tab.c"
    break;

  case 26: /* initline: ilbody  */
#line 118 "parser.y"
                             {(yyval.ia) = (yyvsp[0].ia); (yyval.ia).block=FALSE; (yyval.ia).en = TRUE;}
#line 1422 "parser.tab.c"
    break;

  case 27: /* ilbody: ibinary  */
#line 121 "parser.y"
                             {(yyval.ia) = (yyvsp[0].ia);}
#line 1428 "parser.tab.c"
    break;

  case 28: /* ilbody: ienum  */
#line 122 "parser.y"
                             {(yyval.ia) = (yyvsp[0].ia);}
#line 1434 "parser.tab.c"
    break;

  case 29: /* ilbody: iscalar  */
#line 123 "parser.y"
                             {(yyval.ia) = (yyvsp[0].ia);}
#line 1440 "parser.tab.c"
    break;

  case 30: /* ilbody: isimple  */
#line 124 "parser.y"
                             {(yyval.ia) = (yyvsp[0].ia);}
#line 1446 "parser.tab.c"
    break;

  case 31: /* ilbody: itest  */
#line 125 "parser.y"
                             {(yyval.ia) = (yyvsp[0].ia);}
#line 1452 "parser.tab.c"
    break;

  case 32: /* isimple: CODE  */
#line 128 "parser.y"
                             {(yyval.ia).id=(yyvsp[0].ival);
	                      (yyval.ia).cval.fval=MAXDOUBLE;
	                      (yyval.ia).cval.sval=NULL;}
#line 1460 "parser.tab.c"
    break;

  case 33: /* ibinary: BIN CODE  */
#line 133 "parser.y"
                             {(yyval.ia).id=(yyvsp[0].ival);
	                      (yyval.ia).cval.bval=(yyvsp[-1].ival);
	                      (yyval.ia).cval.fval=MAXDOUBLE;
	                      (yyval.ia).cval.sval=NULL;}
#line 1469 "parser.tab.c"
    break;

  case 34: /* ienum: STATE CODE  */
#line 139 "parser.y"
                             {(yyval.ia).id=(yyvsp[0].ival);
	                      (yyval.ia).cval.ival=(yyvsp[-1].ival);
	                      (yyval.ia).cval.fval=MAXDOUBLE;
	                      (yyval.ia).cval.sval=NULL;}
#line 1478 "parser.tab.c"
    break;

  case 35: /* iscalar: PARM CODE  */
#line 145 "parser.y"
                             {(yyval.ia).cval.fval=(yyvsp[-1].fval);
			      (yyval.ia).id=(yyvsp[0].ival);
	                      (yyval.ia).cval.sval=NULL;}
#line 1486 "parser.tab.c"
    break;

  case 36: /* itest: GFIB ADDR DATA CODE  */
#line 150 "parser.y"
                             {(yyval.ia).cval.ival=(yyvsp[-1].ival);
	                      (yyval.na).cval.fval=MAXDOUBLE;
			      (yyval.ia).id=(yyvsp[0].ival);
	                      (yyval.ia).addr=(yyvsp[-2].ival);}
#line 1495 "parser.tab.c"
    break;

  case 37: /* innerline: nlbody DISAB  */
#line 157 "parser.y"
                             {(yyval.na)=(yyvsp[-1].na); (yyval.na).block=FALSE; (yyval.na).en=FALSE;}
#line 1501 "parser.tab.c"
    break;

  case 38: /* innerline: nlbody BR  */
#line 158 "parser.y"
                             {(yyval.na)=(yyvsp[-1].na); (yyval.na).block=TRUE;  (yyval.na).en=TRUE;}
#line 1507 "parser.tab.c"
    break;

  case 39: /* innerline: nlbody  */
#line 159 "parser.y"
                             {(yyval.na)=(yyvsp[0].na); (yyval.na).block=FALSE; (yyval.na).en=TRUE;}
#line 1513 "parser.tab.c"
    break;

  case 40: /* nlbody: TIME nbinary  */
#line 162 "parser.y"
                             {(yyval.na)=(yyvsp[0].na); (yyval.na).time=(yyvsp[-1].lval);}
#line 1519 "parser.tab.c"
    break;

  case 41: /* nlbody: TIME nenum  */
#line 163 "parser.y"
                             {(yyval.na)=(yyvsp[0].na); (yyval.na).time=(yyvsp[-1].lval);}
#line 1525 "parser.tab.c"
    break;

  case 42: /* nlbody: TIME ramp  */
#line 164 "parser.y"
                             {(yyval.na)=(yyvsp[0].na); (yyval.na).time=(yyvsp[-1].lval);}
#line 1531 "parser.tab.c"
    break;

  case 43: /* nlbody: TIME nscalar  */
#line 165 "parser.y"
                             {(yyval.na)=(yyvsp[0].na); (yyval.na).time=(yyvsp[-1].lval);}
#line 1537 "parser.tab.c"
    break;

  case 44: /* nlbody: TIME nsimple  */
#line 166 "parser.y"
                             {(yyval.na)=(yyvsp[0].na); (yyval.na).time=(yyvsp[-1].lval);}
#line 1543 "parser.tab.c"
    break;

  case 45: /* nlbody: TIME ntest  */
#line 167 "parser.y"
                             {(yyval.na)=(yyvsp[0].na); (yyval.na).time=(yyvsp[-1].lval);}
#line 1549 "parser.tab.c"
    break;

  case 46: /* nsimple: CODE  */
#line 170 "parser.y"
                             {(yyval.na).id=(yyvsp[0].ival);
	                      (yyval.na).ramp=FALSE;
			      (yyval.na).ord=UINT_MAX;
			      (yyval.na).cval.fval=MAXDOUBLE;
	                      (yyval.na).cval.sval=NULL;}
#line 1559 "parser.tab.c"
    break;

  case 47: /* nbinary: BIN CODE  */
#line 178 "parser.y"
                             {(yyval.na).id=(yyvsp[0].ival);
                              (yyval.na).ramp=FALSE;
			      (yyval.na).ord=UINT_MAX;
	                      (yyval.na).cval.bval=(yyvsp[-1].ival);
	                      (yyval.na).cval.fval=MAXDOUBLE;
	                      (yyval.na).cval.sval=NULL;}
#line 1570 "parser.tab.c"
    break;

  case 48: /* nenum: STATE CODE  */
#line 186 "parser.y"
                             {(yyval.na).id=(yyvsp[0].ival);
			      (yyval.na).ramp=FALSE;
			      (yyval.na).ord=UINT_MAX;      
	                      (yyval.na).cval.fval=MAXDOUBLE;
                              (yyval.na).cval.ival=(yyvsp[-1].ival);
	                      (yyval.na).cval.sval=NULL;}
#line 1581 "parser.tab.c"
    break;

  case 49: /* nscalar: PARM CODE  */
#line 195 "parser.y"
                             {(yyval.na).id=(yyvsp[0].ival);
                              (yyval.na).ramp=FALSE;
			      (yyval.na).ord=UINT_MAX;
			      (yyval.na).cval.fval=(yyvsp[-1].fval);
	                      (yyval.na).cval.sval=NULL;}
#line 1591 "parser.tab.c"
    break;

  case 50: /* ntest: GFIB ADDR DATA CODE  */
#line 202 "parser.y"
                             {(yyval.na).id=(yyvsp[0].ival);
                              (yyval.na).ramp=FALSE;
                              (yyval.na).ord=UINT_MAX;
			      (yyval.na).addr=(yyvsp[-2].ival);
			      (yyval.na).cval.ival=(yyvsp[-1].ival);
	                      (yyval.na).cval.fval=MAXDOUBLE;
                              (yyval.na).cval.sval=NULL;}
#line 1603 "parser.tab.c"
    break;

  case 51: /* ramp: RMP PARM TIME STP CODE  */
#line 213 "parser.y"
                                {(yyval.na).id=(yyvsp[0].ival);
                                 (yyval.na).ramp=(yyvsp[-4].ival);
			         (yyval.na).ord=UINT_MAX;
				 (yyval.na).fval=(yyvsp[-3].fval);
	                      	 (yyval.na).cval.sval=NULL;
				 (yyval.na).rt=(yyvsp[-2].lval);
				 (yyval.na).steps=(yyvsp[-1].ival);}
#line 1615 "parser.tab.c"
    break;

  case 52: /* ramp: RMP STATE TIME CODE  */
#line 220 "parser.y"
                                {(yyval.na).id=(yyvsp[0].ival);
                                 (yyval.na).ramp=(yyvsp[-3].ival);
			         (yyval.na).ord=UINT_MAX;
				 (yyval.na).fval=(yyvsp[-2].ival);
				 (yyval.na).cval.fval=MAXDOUBLE;
	                      	 (yyval.na).cval.sval=NULL;
				 (yyval.na).rt=(yyvsp[-1].lval);}
#line 1627 "parser.tab.c"
    break;


#line 1631 "parser.tab.c"

      default: break;
    }
  /* User semantic actions sometimes alter yychar, and that requires
     that yytoken be updated with the new translation.  We take the
     approach of translating immediately before every use of yytoken.
     One alternative is translating here after every semantic action,
     but that translation would be missed if the semantic action invokes
     YYABORT, YYACCEPT, or YYERROR immediately after altering yychar or
     if it invokes YYBACKUP.  In the case of YYABORT or YYACCEPT, an
     incorrect destructor might then be invoked immediately.  In the
     case of YYERROR or YYBACKUP, subsequent parser actions might lead
     to an incorrect destructor call or verbose syntax error message
     before the lookahead is translated.  */
  YY_SYMBOL_PRINT ("-> $$ =", YY_CAST (yysymbol_kind_t, yyr1[yyn]), &yyval, &yyloc);

  YYPOPSTACK (yylen);
  yylen = 0;

  *++yyvsp = yyval;

  /* Now 'shift' the result of the reduction.  Determine what state
     that goes to, based on the state we popped back to and the rule
     number reduced by.  */
  {
    const int yylhs = yyr1[yyn] - YYNTOKENS;
    const int yyi = yypgoto[yylhs] + *yyssp;
    yystate = (0 <= yyi && yyi <= YYLAST && yycheck[yyi] == *yyssp
               ? yytable[yyi]
               : yydefgoto[yylhs]);
  }

  goto yynewstate;


/*--------------------------------------.
| yyerrlab -- here on detecting error.  |
`--------------------------------------*/
yyerrlab:
  /* Make sure we have latest lookahead translation.  See comments at
     user semantic actions for why this is necessary.  */
  yytoken = yychar == YYEMPTY ? YYSYMBOL_YYEMPTY : YYTRANSLATE (yychar);
  /* If not already recovering from an error, report this error.  */
  if (!yyerrstatus)
    {
      ++yynerrs;
      yyerror (YY_("syntax error"));
    }

  if (yyerrstatus == 3)
    {
      /* If just tried and failed to reuse lookahead token after an
         error, discard it.  */

      if (yychar <= YYEOF)
        {
          /* Return failure if at end of input.  */
          if (yychar == YYEOF)
            YYABORT;
        }
      else
        {
          yydestruct ("Error: discarding",
                      yytoken, &yylval);
          yychar = YYEMPTY;
        }
    }

  /* Else will try to reuse lookahead token after shifting the error
     token.  */
  goto yyerrlab1;


/*---------------------------------------------------.
| yyerrorlab -- error raised explicitly by YYERROR.  |
`---------------------------------------------------*/
yyerrorlab:
  /* Pacify compilers when the user code never invokes YYERROR and the
     label yyerrorlab therefore never appears in user code.  */
  if (0)
    YYERROR;

  /* Do not reclaim the symbols of the rule whose action triggered
     this YYERROR.  */
  YYPOPSTACK (yylen);
  yylen = 0;
  YY_STACK_PRINT (yyss, yyssp);
  yystate = *yyssp;
  goto yyerrlab1;


/*-------------------------------------------------------------.
| yyerrlab1 -- common code for both syntax error and YYERROR.  |
`-------------------------------------------------------------*/
yyerrlab1:
  yyerrstatus = 3;      /* Each real token shifted decrements this.  */

  /* Pop stack until we find a state that shifts the error token.  */
  for (;;)
    {
      yyn = yypact[yystate];
      if (!yypact_value_is_default (yyn))
        {
          yyn += YYSYMBOL_YYerror;
          if (0 <= yyn && yyn <= YYLAST && yycheck[yyn] == YYSYMBOL_YYerror)
            {
              yyn = yytable[yyn];
              if (0 < yyn)
                break;
            }
        }

      /* Pop the current state because it cannot handle the error token.  */
      if (yyssp == yyss)
        YYABORT;


      yydestruct ("Error: popping",
                  YY_ACCESSING_SYMBOL (yystate), yyvsp);
      YYPOPSTACK (1);
      yystate = *yyssp;
      YY_STACK_PRINT (yyss, yyssp);
    }

  YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
  *++yyvsp = yylval;
  YY_IGNORE_MAYBE_UNINITIALIZED_END


  /* Shift the error token.  */
  YY_SYMBOL_PRINT ("Shifting", YY_ACCESSING_SYMBOL (yyn), yyvsp, yylsp);

  yystate = yyn;
  goto yynewstate;


/*-------------------------------------.
| yyacceptlab -- YYACCEPT comes here.  |
`-------------------------------------*/
yyacceptlab:
  yyresult = 0;
  goto yyreturn;


/*-----------------------------------.
| yyabortlab -- YYABORT comes here.  |
`-----------------------------------*/
yyabortlab:
  yyresult = 1;
  goto yyreturn;


#if !defined yyoverflow
/*-------------------------------------------------.
| yyexhaustedlab -- memory exhaustion comes here.  |
`-------------------------------------------------*/
yyexhaustedlab:
  yyerror (YY_("memory exhausted"));
  yyresult = 2;
  goto yyreturn;
#endif


/*-------------------------------------------------------.
| yyreturn -- parsing is finished, clean up and return.  |
`-------------------------------------------------------*/
yyreturn:
  if (yychar != YYEMPTY)
    {
      /* Make sure we have latest lookahead translation.  See comments at
         user semantic actions for why this is necessary.  */
      yytoken = YYTRANSLATE (yychar);
      yydestruct ("Cleanup: discarding lookahead",
                  yytoken, &yylval);
    }
  /* Do not reclaim the symbols of the rule whose action triggered
     this YYABORT or YYACCEPT.  */
  YYPOPSTACK (yylen);
  YY_STACK_PRINT (yyss, yyssp);
  while (yyssp != yyss)
    {
      yydestruct ("Cleanup: popping",
                  YY_ACCESSING_SYMBOL (+*yyssp), yyvsp);
      YYPOPSTACK (1);
    }
#ifndef yyoverflow
  if (yyss != yyssa)
    YYSTACK_FREE (yyss);
#endif

  return yyresult;
}

#line 229 "parser.y"


int yyerror(char *er)
{
  return 0;		
}

