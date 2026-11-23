<?php

namespace App\Controller;

final class Login
{
    public function __invoke(Request $request): Response
    {
        $user = $this->users->find($request->get('email'));
        if ($user === null || !password_verify($request->get('password'), $user->hash)) {
            return new Response('Invalid credentials', 401);
        }
        $this->session->set('user', $user->id);
        return new Response('ok');
    }
}
