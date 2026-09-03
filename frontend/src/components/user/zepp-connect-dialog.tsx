import { useState } from 'react';
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  HelpCircle,
  Loader2,
  XCircle,
} from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useConnectZepp, useVerifyZepp } from '@/hooks/api/use-zepp';

interface ZeppConnectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userId: string;
  initialUserId?: string;
  initialHost?: string;
}

const REGIONAL_HOSTS = [
  {
    value: 'api-mifit-us3.zepp.com',
    label: 'Americas / Global (api-mifit-us3.zepp.com) - Padrão',
  },
  {
    value: 'api-mifit-us2.zepp.com',
    label: 'Americas 2 (api-mifit-us2.zepp.com)',
  },
  { value: 'api-mifit-de2.zepp.com', label: 'Europa (api-mifit-de2.zepp.com)' },
  {
    value: 'api-mifit.huami.com',
    label: 'China / Huami (api-mifit.huami.com)',
  },
  { value: 'api-mifit-ru.zepp.com', label: 'Rússia (api-mifit-ru.zepp.com)' },
  { value: 'api-mifit-in2.zepp.com', label: 'Índia (api-mifit-in2.zepp.com)' },
];

export function ZeppConnectDialog({
  open,
  onOpenChange,
  userId,
  initialUserId = '',
  initialHost = 'api-mifit-us3.zepp.com',
}: ZeppConnectDialogProps) {
  const [appToken, setAppToken] = useState('');
  const [zeppUserId, setZeppUserId] = useState(initialUserId);
  const [host, setHost] = useState(initialHost);
  const [quickPaste, setQuickPaste] = useState('');
  const [showGuide, setShowGuide] = useState(false);
  const [activeTab, setActiveTab] = useState<'form' | 'paste'>('form');
  const [verifyStatus, setVerifyStatus] = useState<{
    valid?: boolean;
    message?: string;
  } | null>(null);

  const verifyMutation = useVerifyZepp();
  const connectMutation = useConnectZepp(userId);

  const handleQuickPasteApply = () => {
    let cleanInput = quickPaste.trim();
    if (cleanInput.startsWith('```')) {
      cleanInput = cleanInput
        .replace(/^```(?:json)?\s*/i, '')
        .replace(/\s*```$/, '')
        .trim();
    }

    let token = '';
    let uid = '';
    let h = '';

    try {
      const parsed = JSON.parse(cleanInput);

      if (Array.isArray(parsed)) {
        for (const item of parsed) {
          if (typeof item === 'object' && item !== null) {
            const k = String(
              item.name || item.key || item.header || ''
            ).toLowerCase();
            const v = String(item.value || '');
            if (k === 'apptoken' || k === 'app_token' || k === 'token')
              token = v;
            if (k === 'userid' || k === 'user_id') uid = v;
            if (k === 'host') h = v;
          }
        }
      } else if (typeof parsed === 'object' && parsed !== null) {
        const headers =
          (parsed.headers as Record<string, unknown>) ||
          (parsed.header as Record<string, unknown>) ||
          {};
        token = String(
          parsed.app_token ||
            parsed.apptoken ||
            parsed.token ||
            parsed.access_token ||
            headers.apptoken ||
            headers.app_token ||
            headers['app-token'] ||
            ''
        );
        uid = String(
          parsed.user_id ||
            parsed.userid ||
            parsed.userId ||
            headers.userid ||
            headers.user_id ||
            ''
        );
        h = String(parsed.host || parsed.api_host || headers.host || '');
      }
    } catch {
      // Fall through to regex parsing below
    }

    if (!token) {
      const tokenMatch = cleanInput.match(
        /(?:app_?token|access_token|token)[:=\s"']+\s*([a-zA-Z0-9_\-./+=%]+)/i
      );
      if (tokenMatch) token = tokenMatch[1];
    }
    if (!uid) {
      const uidMatch = cleanInput.match(
        /(?:userid|user_id)[:=\s"']+\s*([0-9]+)/i
      );
      if (uidMatch) uid = uidMatch[1];
    }
    if (!h) {
      const hostMatch = cleanInput.match(
        /(?:https?:\/\/)?([a-zA-Z0-9.-]*zepp\.com|[a-zA-Z0-9.-]*huami\.com)/i
      );
      if (hostMatch) h = hostMatch[1];
    }

    let found = false;
    if (token) {
      setAppToken(token.trim());
      found = true;
    }
    if (uid) {
      setZeppUserId(uid.trim());
      found = true;
    }
    if (h) {
      let cleanHost = h.trim().toLowerCase();
      if (cleanHost.includes('://')) cleanHost = cleanHost.split('://')[1];
      cleanHost = cleanHost.split('/')[0].split(':')[0];
      const match = REGIONAL_HOSTS.find((r) => r.value === cleanHost);
      if (match) {
        setHost(match.value);
      } else {
        setHost(cleanHost);
      }
      found = true;
    }

    if (found) {
      setVerifyStatus(null);
      setActiveTab('form');
      toast.success('Valores extraídos e aplicados com sucesso!');
    } else {
      toast.error(
        'Não foi possível identificar o token ou userid no texto colado.'
      );
    }
  };

  const handleVerify = async () => {
    if (!appToken.trim() || !zeppUserId.trim()) {
      toast.error('Preencha o App Token e o User ID do Zepp.');
      return;
    }
    setVerifyStatus(null);
    try {
      const res = await verifyMutation.mutateAsync({
        app_token: appToken.trim(),
        user_id: zeppUserId.trim(),
        host: host.trim(),
      });
      setVerifyStatus({
        valid: res.valid,
        message: res.valid
          ? 'Credenciais válidas! Conexão testada com sucesso.'
          : res.message || 'Credenciais inválidas ou token expirado.',
      });
    } catch (err: unknown) {
      setVerifyStatus({
        valid: false,
        message:
          err instanceof Error ? err.message : 'Erro ao verificar credenciais.',
      });
    }
  };

  const handleConnect = async () => {
    if (!appToken.trim() || !zeppUserId.trim()) {
      toast.error('Preencha o App Token e o User ID do Zepp.');
      return;
    }
    try {
      await connectMutation.mutateAsync({
        app_token: appToken.trim(),
        provider_user_id: zeppUserId.trim(),
        host: host.trim(),
      });
      onOpenChange(false);
    } catch {
      // Error handled by hook toast
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <img
              src="/api/v1/meta/provider-icons/zepp.svg"
              alt="Zepp"
              className="h-6 w-6 object-contain"
              onError={(e) => {
                // Fallback if svg icon endpoint isn't loaded yet
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
            Conectar Relógio Amazfit / Zepp
          </DialogTitle>
          <DialogDescription>
            Conecte sua conta Zepp através do App Token e User ID da sessão
            mobile para sincronizar treinos, sono, passos, frequência cardíaca e
            pontuações de saúde.
          </DialogDescription>
        </DialogHeader>

        <Tabs
          value={activeTab}
          onValueChange={(val) => setActiveTab(val as 'form' | 'paste')}
          className="w-full"
        >
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="form">Credenciais Diretas</TabsTrigger>
            <TabsTrigger value="paste">Colar JSON / Headers</TabsTrigger>
          </TabsList>

          <TabsContent value="form" className="space-y-4 pt-3">
            <div className="space-y-2">
              <Label htmlFor="zepp-token">App Token *</Label>
              <Input
                id="zepp-token"
                type="password"
                placeholder="your-app-token-here"
                value={appToken}
                onChange={(e) => {
                  setAppToken(e.target.value);
                  setVerifyStatus(null);
                }}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="zepp-uid">User ID Zepp *</Label>
                <Input
                  id="zepp-uid"
                  placeholder="your-user-id-here"
                  value={zeppUserId}
                  onChange={(e) => {
                    setZeppUserId(e.target.value);
                    setVerifyStatus(null);
                  }}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="zepp-host">Servidor Regional</Label>
                <select
                  id="zepp-host"
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  value={host}
                  onChange={(e) => {
                    setHost(e.target.value);
                    setVerifyStatus(null);
                  }}
                >
                  {REGIONAL_HOSTS.map((h) => (
                    <option key={h.value} value={h.value}>
                      {h.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="paste" className="space-y-3 pt-3">
            <div className="space-y-2">
              <Label htmlFor="quick-paste">
                Cole o JSON de exportação ou requisição HTTP
              </Label>
              <textarea
                id="quick-paste"
                className="w-full min-h-[120px] rounded-md border border-input bg-background p-3 text-xs font-mono shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                placeholder='Ex: {"app_token": "your-app-token-here", "user_id": "your-user-id-here", "host": "api-mifit-us3.zepp.com"}'
                value={quickPaste}
                onChange={(e) => setQuickPaste(e.target.value)}
              />
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleQuickPasteApply}
            >
              Extrair e Aplicar aos Campos
            </Button>
          </TabsContent>
        </Tabs>

        {/* Verification feedback */}
        {verifyStatus && (
          <div
            className={`flex items-start gap-2.5 rounded-lg border p-3 text-xs ${
              verifyStatus.valid
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                : 'border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-400'
            }`}
          >
            {verifyStatus.valid ? (
              <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
            ) : (
              <XCircle className="h-4 w-4 mt-0.5 shrink-0" />
            )}
            <div>
              <p className="font-semibold">
                {verifyStatus.valid
                  ? 'Credenciais Válidas'
                  : 'Falha na Validação'}
              </p>
              <p className="mt-0.5 opacity-90">{verifyStatus.message}</p>
            </div>
          </div>
        )}

        {/* Guide toggle */}
        <div className="border-t pt-3">
          <button
            type="button"
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => setShowGuide(!showGuide)}
          >
            <HelpCircle className="h-3.5 w-3.5" />
            <span>Como obter o App Token e User ID do Zepp?</span>
            {showGuide ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </button>

          {showGuide && (
            <div className="mt-2 rounded-md bg-muted/60 p-3 text-xs space-y-2 text-muted-foreground">
              <p className="font-medium text-foreground">
                Instruções de extração rápida:
              </p>
              <ol className="list-decimal list-inside space-y-1">
                <li>
                  Abra um proxy de rede (como HTTP Toolkit, mitmproxy, Charles
                  ou Reqable) no PC ou celular.
                </li>
                <li>
                  Abra o aplicativo Zepp no smartphone e sincronize o relógio.
                </li>
                <li>
                  Filtre requisições para <code>*.zepp.com</code> ou{' '}
                  <code>*.huami.com</code>.
                </li>
                <li>
                  Localize qualquer chamada (ex:{' '}
                  <code>/huami.health.getUserInfo.json</code>).
                </li>
                <li>
                  Copie o header <code>apptoken</code> e o parâmetro{' '}
                  <code>userid</code>.
                </li>
              </ol>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            type="button"
            variant="outline"
            onClick={handleVerify}
            disabled={verifyMutation.isPending || connectMutation.isPending}
          >
            {verifyMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Testar Credenciais
          </Button>

          <Button
            type="button"
            onClick={handleConnect}
            disabled={connectMutation.isPending || verifyMutation.isPending}
          >
            {connectMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Salvar e Conectar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
